import datetime
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.request import pathname2url

import attr
import magic
import pyclamd
import requests
import volatility3.plugins
import vt
from asgiref.sync import async_to_sync
from bs4 import BeautifulSoup
from channels.layers import get_channel_layer
from distributed import get_client, rejoin, secede
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from elasticsearch import Elasticsearch, helpers
from elasticsearch_dsl import Search
from guardian.shortcuts import get_users_with_perms
from regipy.registry import RegistryHive
from volatility3 import framework
from volatility3.cli.text_renderer import (
    JsonRenderer,
    display_disassembly,
    format_hints,
    hex_bytes_as_text,
    multitypedata_as_text,
    optional,
    quoted_optional,
)
from volatility3.framework import (
    automagic,
    constants,
    contexts,
    exceptions,
    interfaces,
    plugins,
)
from volatility3.framework.automagic import stacker
from volatility3.framework.configuration import requirements
from volatility3.framework.configuration.requirements import (
    ChoiceRequirement,
    ListRequirement,
)

from orochi.website.models import (
    DUMP_STATUS_COMPLETED,
    DUMP_STATUS_ERROR,
    RESULT_STATUS_DISABLED,
    RESULT_STATUS_EMPTY,
    RESULT_STATUS_ERROR,
    RESULT_STATUS_SUCCESS,
    RESULT_STATUS_UNSATISFIED,
    SERVICE_VIRUSTOTAL,
    CustomRule,
    Dump,
    ExtractedDump,
    Result,
    Service,
)

BANNER_REGEX = r'^"?Linux version (?P<kernel>\S+) (?P<build>.+) \(((?P<gcc>gcc.+)) #(?P<number>\d+)(?P<info>.+)$"?'


class MuteProgress(object):
    """
    Mutes progress for volatility plugin
    """

    def __init__(self):
        self._max_message_len = 0

    def __call__(self, progress: Union[int, float], description: Optional[str] = None):
        pass


def file_handler_class_factory(output_dir, file_list):
    class NullFileHandler(io.BytesIO, interfaces.plugins.FileHandlerInterface):
        """Null FileHandler that swallows files whole without consuming memory"""

        def __init__(self, preferred_name: str):
            interfaces.plugins.FileHandlerInterface.__init__(self, preferred_name)
            super().__init__()

        def writelines(self, lines):
            """Dummy method"""
            pass

        def write(self, data):
            """Dummy method"""
            return len(data)

    class OrochiFileHandler(interfaces.plugins.FileHandlerInterface):
        def __init__(self, filename: str):
            fd, self._name = tempfile.mkstemp(suffix=".vol3", prefix="tmp_")
            self._file = io.open(fd, mode="w+b")
            interfaces.plugins.FileHandlerInterface.__init__(self, filename)
            for item in dir(self._file):
                if not item.startswith("_") and item not in [
                    "closed",
                    "close",
                    "mode",
                    "name",
                ]:
                    setattr(self, item, getattr(self._file, item))

        def __getattr__(self, item):
            return getattr(self._file, item)

        @property
        def closed(self):
            return self._file.closed

        @property
        def mode(self):
            return self._file.mode

        @property
        def name(self):
            return self._file.name

        def getvalue(self) -> bytes:
            """Mimic a BytesIO object's getvalue parameter"""
            # Opens the file new so we're not trying to do IO on a closed file
            with open(self._name, mode="rb") as this_file:
                return this_file.read()

        def delete(self):
            self.close()
            os.remove(self._name)

        def close(self):
            """Closes and commits the file (by moving the temporary file to the correct name"""
            # Don't overcommit
            if self._file.closed:
                return
            self._file.close()
            file_list.append(self)

    return OrochiFileHandler if output_dir else NullFileHandler


class ReturnJsonRenderer(JsonRenderer):
    """
    Custom json renderer that doesn't write json on disk but returns it with errors if present
    """

    _type_renderers = {
        format_hints.HexBytes: quoted_optional(hex_bytes_as_text),
        interfaces.renderers.Disassembly: quoted_optional(display_disassembly),
        format_hints.MultiTypeData: quoted_optional(multitypedata_as_text),
        format_hints.Hex: optional(lambda x: f"0x{x:x}"),
        format_hints.Bin: optional(lambda x: f"0x{x:b}"),
        bytes: optional(lambda x: " ".join([f"{b:02x}" for b in x])),
        datetime.datetime: lambda x: None
        if isinstance(x, interfaces.renderers.BaseAbsentValue)
        else x.isoformat(),
        "default": quoted_optional(lambda x: f"{x}"),
    }

    def render(self, grid: interfaces.renderers.TreeGrid):
        final_output = ({}, [])

        def visitor(
            node: interfaces.renderers.TreeNode,
            accumulator: Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]],
        ) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
            # Nodes always have a path value, giving them a path_depth of at least 1, we use max just in case
            acc_map, final_tree = accumulator
            node_dict = {"__children": []}
            for column_index in range(len(grid.columns)):
                column = grid.columns[column_index]
                renderer = self._type_renderers.get(
                    column.type, self._type_renderers["default"]
                )
                data = renderer(list(node.values)[column_index])
                if isinstance(data, interfaces.renderers.BaseAbsentValue):
                    data = None
                node_dict[column.name] = data
            if node.parent:
                acc_map[node.parent.path]["__children"].append(node_dict)
            else:
                final_tree.append(node_dict)
            acc_map[node.path] = node_dict
            return (acc_map, final_tree)

        error = grid.populate(visitor, final_output, fail_on_errors=False)
        return final_output[1], error


def gendata(index, result, other_info):
    """
    Elastic bulk insert generator
    """
    for item in result:
        item.update(other_info)
        yield {"_index": index, "_id": uuid.uuid4(), "_source": item}


def hash_checksum(filename, block_size=65536):
    """
    Generate hashes for filename
    """
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
            md5.update(block)
    return sha256.hexdigest(), md5.hexdigest()


def get_parameters(plugin):
    """
    Obtains parameters list from volatility plugin
    """
    _ = contexts.Context()
    _ = framework.import_files(volatility3.plugins, True)
    plugin_list = framework.list_plugins()
    params = []
    if plugin in plugin_list:
        for requirement in plugin_list[plugin].get_requirements():
            additional = {"optional": requirement.optional, "name": requirement.name}

            if isinstance(requirement, requirements.URIRequirement):
                additional["mode"] = "single"
                additional["type"] = "file"
            elif isinstance(
                requirement, interfaces.configuration.SimpleTypeRequirement
            ):
                additional["mode"] = "single"
                additional["type"] = requirement.instance_type
            elif isinstance(requirement, ListRequirement):
                additional["mode"] = "list"
                additional["type"] = requirement.element_type
            elif isinstance(requirement, ChoiceRequirement):
                additional["type"] = str
                additional["mode"] = "single"
                additional["choices"] = requirement.choices
            else:
                continue
            params.append(additional)
    return params


def run_vt(result_pk, filepath):
    """
    Runs virustotal on filepath
    """
    try:
        vt_service = Service.objects.get(name=SERVICE_VIRUSTOTAL)
        vt_client = vt.Client(vt_service.key, proxy=vt_service.proxy)
        try:
            report = vt_client.get_object(f"/files/{hash_checksum(filepath)[0]}")
            stats = report.last_analysis_stats or {}
            scan_date = (
                report.last_analysis_date.timestamp()
                if report.last_analysis_date
                else None
            )
            vt_report = {
                "last_analysis_stats": stats,
                "scan_date": scan_date,
                "positives": stats.get("malicious", 0) + stats.get("suspicious", 0),
                "total": sum(stats.get(x, 0) for x in stats.keys()) if stats else 0,
                "permalink": f"https://www.virustotal.com/api/v3/files/{report.id}",
            }
            vt_client.close()

        except vt.error.APIError as excp:
            vt_report = {"error": f"{excp}"}
    except ObjectDoesNotExist:
        vt_report = {"error": "Service not configured"}

    ed = ExtractedDump.objects.get(result__pk=result_pk, path=filepath)
    ed.vt_report = vt_report
    ed.save()


def run_regipy(result_pk, filepath):
    """
    Runs regipy on filepath
    """
    try:
        registry_hive = RegistryHive(filepath)
        reg_json = registry_hive.recurse_subkeys(registry_hive.root, as_json=True)
        root = {"values": [attr.asdict(entry) for entry in reg_json]}
        root = json.loads(json.dumps(root).replace(r"\u0000", ""))
    except Exception as e:
        logging.error(e)
        root = {}

    ed = ExtractedDump.objects.get(result__pk=result_pk, path=filepath)
    ed.reg_array = root
    ed.save()


def run_maxmind(result_pk, filepath):
    pass


def send_to_ws(dump, result=None, plugin_name=None, message=None, color=None):
    """
    Notifies plugin result to websocket
    """
    colors = {1: "green", 2: "green", 3: "orange", 4: "red"}

    users = get_users_with_perms(dump, only_with_perms_in=["can_see"])

    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    for user in users:
        if result and plugin_name:
            async_to_sync(channel_layer.group_send)(
                f"chat_{user.pk}",
                {
                    "type": "chat_message",
                    "message": f"""{datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}||"""
                    f"""Plugin <b>{plugin_name}</b> on dump <b>{dump.name}</b> ended<br>"""
                    f"""Status: <b style='color:{colors[result.result]}'>{result.get_result_display()}</b>""",
                },
            )
        elif message and color:
            async_to_sync(channel_layer.group_send)(
                f"chat_{user.pk}",
                {
                    "type": "chat_message",
                    "message": f"""{datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}||"""
                    f"""Message on dump <b>{dump.name}</b><br><b style='color:{colors[color]}'>{message}</b>""",
                },
            )


def run_plugin(dump_obj, plugin_obj, params=None, user_pk=None):
    """
    Execute a single plugin on a dump with optional params.
    If success data are sent to elastic.
    """
    logging.info("[dump {} - plugin {}] start".format(dump_obj.pk, plugin_obj.pk))
    try:
        ctx = contexts.Context()
        constants.PARALLELISM = constants.Parallelism.Off
        _ = framework.import_files(volatility3.plugins, True)
        automagics = automagic.available(ctx)
        plugin_list = framework.list_plugins()
        json_renderer = ReturnJsonRenderer
        seen_automagics = set()
        for amagic in automagics:
            if amagic in seen_automagics:
                continue
            seen_automagics.add(amagic)
        plugin = plugin_list.get(plugin_obj.name)
        base_config_path = "plugins"
        file_name = os.path.abspath(dump_obj.upload.path)
        single_location = "file:" + pathname2url(file_name)
        ctx.config["automagic.LayerStacker.single_location"] = single_location
        automagics = automagic.choose_automagic(automagics, plugin)
        if ctx.config.get("automagic.LayerStacker.stackers", None) is None:
            ctx.config["automagic.LayerStacker.stackers"] = stacker.choose_os_stackers(
                plugin
            )
        # LOCAL DUMPS REQUIRES FILES
        local_dump = plugin_obj.local_dump

        # ADD PARAMETERS, AND IF LOCAL DUMP ENABLE ADD DUMP TRUE BY DEFAULT
        plugin_config_path = interfaces.configuration.path_join(
            base_config_path, plugin.__name__
        )
        if params:
            # ADD PARAMETERS TO PLUGIN CONF
            for k, v in params.items():
                if v != "":
                    extended_path = interfaces.configuration.path_join(
                        plugin_config_path, k
                    )
                    ctx.config[extended_path] = v

                if k == "dump" and v:
                    # IF DUMP TRUE HAS BEEN PASS IT'LL DUMP LOCALLY
                    local_dump = True

        if not params and local_dump:
            # IF ADMIN SET LOCAL DUMP ADD DUMP TRUE AS PARAMETER
            extended_path = interfaces.configuration.path_join(
                plugin_config_path, "dump"
            )
            ctx.config[extended_path] = True

        logging.debug(
            "[dump {} - plugin {}] params: {}".format(
                dump_obj.pk, plugin_obj.pk, ctx.config
            )
        )

        file_list = []
        if local_dump:
            # IF PARAM/ADMIN DUMP CREATE FILECONSUMER
            local_path = "{}/{}/{}".format(
                settings.MEDIA_ROOT, dump_obj.index, plugin_obj.name
            )
            if not os.path.exists(local_path):
                os.mkdir(local_path)
            file_handler = file_handler_class_factory(
                output_dir=local_path, file_list=file_list
            )
        else:
            local_path = None
            file_handler = file_handler_class_factory(
                output_dir=None, file_list=file_list
            )

        # #####################
        # ## YARA
        # if not file or rule selected and exists default use that
        if plugin_obj.name in ["yarascan.YaraScan", "windows.vadyarascan.VadYaraScan"]:
            if not params:
                has_file = False
            else:
                has_file = False
                for k, v in params.items():
                    if k in ["yara_file", "yara_compiled_file", "yara_rules"] and (
                        v is not None and v != ""
                    ):
                        has_file = True

            if not has_file:
                rule = CustomRule.objects.get(user__pk=user_pk, default=True)
                if rule:
                    extended_path = interfaces.configuration.path_join(
                        plugin_config_path, "yara_compiled_file"
                    )
                    ctx.config[extended_path] = "file:{}".format(rule.path)

            logging.error(
                "[dump {} - plugin {}] params: {}".format(
                    dump_obj.pk, plugin_obj.pk, ctx.config
                )
            )

        try:
            # RUN PLUGIN
            constructed = plugins.construct_plugin(
                ctx,
                automagics,
                plugin,
                base_config_path,
                MuteProgress(),
                file_handler,
            )
        except exceptions.UnsatisfiedException as excp:
            # LOG UNSATISFIED ERROR
            result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)
            result.result = RESULT_STATUS_UNSATISFIED
            result.description = "\n".join(
                [
                    excp.unsatisfied[config_path].description
                    for config_path in excp.unsatisfied
                ]
            )
            result.save()
            send_to_ws(dump_obj, result, plugin_obj.name)

            logging.error(
                "[dump {} - plugin {}] unsatisfied".format(dump_obj.pk, plugin_obj.pk)
            )

            return 0
        try:
            runned_plugin = constructed.run()
        except Exception as excp:
            # LOG GENERIC ERROR [VOLATILITY]
            fulltrace = traceback.TracebackException.from_exception(excp).format(
                chain=True
            )
            result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)
            result.result = RESULT_STATUS_ERROR
            result.description = "\n".join(fulltrace)
            result.save()
            send_to_ws(dump_obj, result, plugin_obj.name)
            logging.error(
                "[dump {} - plugin {}] generic error".format(dump_obj.pk, plugin_obj.pk)
            )
            return 0

        # RENDER OUTPUT IN JSON AND PUT IT IN ELASTIC
        json_data, error = json_renderer().render(runned_plugin)

        logging.debug("DATA: {}".format(json_data))
        logging.debug("ERROR: {}".format(error))
        logging.debug("CONFIG: {}".format(ctx.config))

        if len(json_data) > 0:
            # IF DUMP STORE FILE ON DISK
            if local_dump and file_list:
                for file_id in file_list:
                    output_path = "{}/{}".format(local_path, file_id.preferred_filename)
                    with open(output_path, "wb") as f:
                        f.write(file_id.getvalue())

                # RUN CLAMAV ON ALL FOLDER
                if plugin_obj.clamav_check:
                    cd = pyclamd.ClamdUnixSocket()
                    match = cd.multiscan_file(local_path)
                    match = match or {}
                else:
                    match = {}

                result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)

                # BULK CREATE EXTRACTED DUMP FOR EACH DUMPED FILE
                ExtractedDump.objects.bulk_create(
                    [
                        ExtractedDump(
                            result=result,
                            path="{}/{}".format(local_path, file_id.preferred_filename),
                            sha256=hash_checksum(
                                "{}/{}".format(local_path, file_id.preferred_filename)
                            )[0],
                            md5=hash_checksum(
                                "{}/{}".format(local_path, file_id.preferred_filename)
                            )[1],
                            clamav=(
                                match[
                                    "{}/{}".format(
                                        local_path,
                                        file_id.preferred_filename,
                                    )
                                ][1]
                                if "{}/{}".format(
                                    local_path, file_id.preferred_filename
                                )
                                in match.keys()
                                else None
                            ),
                        )
                        for file_id in file_list
                    ]
                )

                # RUN VT AND REGIPY AS DASK SUBTASKS
                if plugin_obj.vt_check or plugin_obj.regipy_check:
                    dask_client = get_client()
                    secede()
                    tasks = []
                    for file_id in file_list:
                        if plugin_obj.vt_check:
                            task = dask_client.submit(
                                run_vt,
                                result.pk,
                                "{}/{}".format(local_path, file_id.preferred_filename),
                            )
                            tasks.append(task)
                        if plugin_obj.regipy_check:
                            task = dask_client.submit(
                                run_regipy,
                                result.pk,
                                "{}/{}".format(local_path, file_id.preferred_filename),
                            )
                            tasks.append(task)
                    _ = dask_client.gather(tasks)
                    rejoin()

            es = Elasticsearch(
                [settings.ELASTICSEARCH_URL],
                request_timeout=60,
                max_retries=10,
                retry_on_timeout=True,
            )
            helpers.bulk(
                es,
                gendata(
                    "{}_{}".format(dump_obj.index, plugin_obj.name.lower()),
                    json_data,
                    {
                        "dump_name": dump_obj.name,
                        "orochi_plugin": plugin_obj.name.lower(),
                        "orochi_os": dump_obj.get_operating_system_display(),
                        "orochi_createdAt": datetime.datetime.now()
                        .replace(microsecond=0)
                        .isoformat(),
                    },
                ),
            )

            # set max_windows_size on new created index
            es.indices.put_settings(
                index="{}_{}".format(dump_obj.index, plugin_obj.name.lower()),
                body={
                    "index": {"max_result_window": settings.MAX_ELASTIC_WINDOWS_SIZE}
                },
            )

            # EVERYTHING OK
            result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)
            result.result = RESULT_STATUS_SUCCESS
            result.description = error
            result.save()

            logging.debug(
                "[dump {} - plugin {}] sent to elastic".format(
                    dump_obj.pk, plugin_obj.pk
                )
            )
        else:
            # OK BUT EMPTY
            result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)
            result.result = RESULT_STATUS_EMPTY
            result.description = error
            result.save()

            logging.debug(
                "[dump {} - plugin {}] empty".format(dump_obj.pk, plugin_obj.pk)
            )
        send_to_ws(dump_obj, result, plugin_obj.name)
        return 0

    except Exception as excp:
        # LOG GENERIC ERROR [ELASTIC]
        fulltrace = traceback.TracebackException.from_exception(excp).format(chain=True)
        result = Result.objects.get(plugin=plugin_obj, dump=dump_obj)
        result.result = RESULT_STATUS_ERROR
        result.description = "\n".join(fulltrace)
        result.save()
        send_to_ws(dump_obj, result, plugin_obj.name)
        logging.error(
            "[dump {} - plugin {}] generic error".format(dump_obj.pk, plugin_obj.pk)
        )
        return 0


def get_path_from_banner(banner):
    """
    Find web url for symbols parsing banner
    """
    if m := re.match(BANNER_REGEX, banner):
        m.groupdict()

        # UBUNTU
        if "ubuntu" in m["gcc"].lower() or "ubuntu" in m["info"].lower():
            arch = None
            if banner.lower().find("amd64") != -1:
                arch = "amd64"
            elif banner.lower().find("arm64") != -1:
                arch = "arm64"
            elif banner.lower().find("i386") != -1:
                arch = "i386"
            else:
                return ["[OS wip] insert here symbols url!"]
            package_name = "linux-image-{}".format(m["kernel"])
            package_alternative_name = "linux-image-unsigned-{}".format(m["kernel"])
            url = "http://ddebs.ubuntu.com/ubuntu/pool/main/l/linux/"
            try:
                html_text = requests.get(url).text
                soup = BeautifulSoup(html_text, "html.parser")
                for link in soup.find_all("a"):
                    if link.get("href", None):
                        if (
                            link.get("href").find(package_name) != -1
                            and link.get("href").find(arch) != -1
                        ):
                            down_url = "{}{}".format(url, link.get("href"))
                            return [down_url]
                        if (
                            link.get("href").find(package_alternative_name) != -1
                            and link.get("href").find(arch) != -1
                        ):
                            down_url = "{}{}".format(url, link.get("href"))
                            return [down_url]
            except:
                return ["[Download fail] insert here symbols url!"]

        # DEBIAN
        elif "debian" in m["gcc"].lower() or "debian" in m["info"].lower():
            arch = None
            if banner.lower().find("amd64") != -1:
                arch = "amd64"
            elif banner.lower().find("arm64") != -1:
                arch = "arm64"
            elif banner.lower().find("i386") != -1:
                arch = "i386"
            else:
                return ["[OS wip] insert here symbols url!"]
            package_name = "linux-image-{}-dbg".format(m["kernel"])
            try:
                url = "https://deb.sipwise.com/debian/pool/main/l/linux/"
                html_text = requests.get(url).text
                soup = BeautifulSoup(html_text, "html.parser")
                for link in soup.find_all("a"):
                    href = link.get("href", None)
                    if href and link.get("href").find(package_name) != -1:
                        try:
                            p_kernel, p_info, p_arch = href.split("_")
                            p_arch = p_arch.split(".")[0]
                            if (
                                p_kernel.find(package_name) != -1
                                and m["info"].find(p_info) != -1
                                and p_arch == arch
                            ):
                                down_url = "{}{}".format(url, href)
                                return [down_url]
                        except:
                            print(href.split("_"))
                            return ["[Download fail] insert here symbols url!"]
            except:
                return ["[Download fail] insert here symbols url!"]
        else:
            return ["[OS wip] insert here symbols url!"]
    return ["[Banner parse fail] insert here symbols url!"]


def get_banner(result):
    """
    Get banner from elastic for a specific dump. If multiple gets first
    """
    es_client = Elasticsearch([settings.ELASTICSEARCH_URL])
    s = Search(
        using=es_client,
        index="{}_{}".format(result.dump.index, result.plugin.name.lower()),
    )
    banners = [hit.to_dict().get("Banner", None) for hit in s.execute()]
    logging.error("banners: {}".format(banners))
    if len(banners) > 0:
        for hit in banners:
            logging.debug("[dump {}] symbol hit: {}".format(result.dump.pk, hit))
        return banners[0]  # hopefully they are always the same
    logging.error("[dump {}] no hit".format(result.dump.pk))
    return None


def check_runnable(dump_pk, operating_system, banner):
    """
    Checks if dump's banner is available in banner cache
    """
    if operating_system == "Windows":
        logging.error("NO YET IMPLEMENTED WINDOWS CHECk")
        return True
    if operating_system == "Mac":
        logging.error("NO YET IMPLEMENTED MAC CHECk")
        return True
    if operating_system == "Linux":
        if not banner:
            logging.error(
                "[dump {}] {} missing banner".format(dump_pk, operating_system)
            )
            return False

        dump_kernel = None

        if m := re.match(BANNER_REGEX, banner):
            m.groupdict()
            dump_kernel = m["kernel"]
        else:
            logging.error("Error extracting kernel info from dump")

        ctx = contexts.Context()
        automagics = automagic.available(ctx)
        if banners := [
            x for x in automagics if x._config_path == "automagic.LinuxSymbolFinder"
        ]:
            for active_banner in banners[0].banners:
                if not active_banner:
                    continue
                active_banner = active_banner.rstrip(b"\n\00")
                if m := re.match(BANNER_REGEX, active_banner.decode("utf-8")):
                    m.groupdict()
                    if m["kernel"] == dump_kernel:
                        return True
                else:
                    logging.error("Error extracting kernel info from dump")
            logging.error("[dump {}] Banner not found".format(dump_pk))
            logging.error(
                "Available banners: {}".format(
                    [
                        "\n\t- {}".format(available_banner)
                        for available_banner in banners
                    ]
                )
            )
            logging.error("Searched banner:\n\t- {}".format(banner))
            return False
        logging.error("[dump {}] Failure looking for banners".format(dump_pk))
        return False
    return False


def unzip_then_run(dump_pk, user_pk, password, restart):
    dump = Dump.objects.get(pk=dump_pk)
    logging.debug("[dump {}] Processing".format(dump_pk))

    if not restart:
        # COPY EACH FILE IN THEIR FOLDER BEFORE UNZIP/RUN PLUGIN
        extract_path = f"{settings.MEDIA_ROOT}/{dump.index}"
        filepath = shutil.move(dump.upload.path, extract_path)

        filetype = magic.from_file(filepath, mime=True)
        if filetype in [
            "application/zip",
            "application/x-7z-compressed",
            "application/x-rar",
            "application/gzip",
            "application/x-tar",
        ]:
            if password:
                subprocess.call(
                    [
                        "7z",
                        "e",
                        f"{filepath}",
                        f"-o{extract_path}",
                        f"-p{password}",
                        "-y",
                    ]
                )
            else:
                subprocess.call(["7z", "e", f"{filepath}", f"-o{extract_path}", "-y"])

            os.unlink(filepath)
            extracted_files = [
                str(x) for x in Path(extract_path).glob("**/*") if x.is_file()
            ]
            newpath = None
            if len(extracted_files) == 1:
                newpath = extracted_files[0]
            elif len(extracted_files) > 1:
                for x in extracted_files:
                    if x.lower().endswith(".vmem"):
                        newpath = Path(extract_path, x)
            if not newpath:
                # archive is unvalid
                logging.error("[dump {}] Invalid archive dump data".format(dump_pk))
                dump.status = DUMP_STATUS_ERROR
                dump.save()
                return
        else:
            newpath = filepath

        dump.upload.name = newpath
        dump.size = os.path.getsize(newpath)
        sha256, md5 = hash_checksum(newpath)
        dump.sha256 = sha256
        dump.md5 = md5
        dump.save()
        banner = False

        # check symbols using banners
        if dump.operating_system in ("Linux", "Mac"):
            # results already exists because all plugin results are created when dump is created
            banner = dump.result_set.get(plugin__name="banners.Banners")
            if banner:
                banner.result = 0
                banner.save()
                run_plugin(dump, banner.plugin)
                time.sleep(1)
                banner_result = get_banner(banner)
                if banner_result:
                    dump.banner = banner_result.strip("\"'")
                    logging.error(
                        "[dump {}] guessed banner '{}'".format(dump_pk, dump.banner)
                    )
                    dump.save()

    if restart or check_runnable(dump.pk, dump.operating_system, dump.banner):
        dask_client = get_client()
        secede()
        tasks = []
        tasks_list = (
            dump.result_set.all()
            if dump.operating_system != "Linux"
            else dump.result_set.exclude(plugin__name="banners.Banners")
        )
        if restart:
            tasks_list = tasks_list.filter(plugin__pk__in=restart)
        for result in tasks_list:
            if result.result != RESULT_STATUS_DISABLED:
                task = dask_client.submit(
                    run_plugin, dump, result.plugin, None, user_pk
                )
                tasks.append(task)
        _ = dask_client.gather(tasks)
        logging.debug("[dump {}] tasks submitted".format(dump_pk))
        rejoin()
        dump.status = DUMP_STATUS_COMPLETED
        dump.save()
        logging.debug("[dump {}] processing terminated".format(dump_pk))
    else:
        # This takes time so we do this one time only
        if dump.banner:
            dump.suggested_symbols_path = get_path_from_banner(dump.banner)
        dump.missing_symbols = True
        dump.status = DUMP_STATUS_COMPLETED
        dump.save()
        logging.error(
            "[dump {}] symbols non available. Disabling all plugins".format(dump_pk)
        )
        tasks_list = (
            dump.result_set.all()
            if dump.operating_system != "Linux"
            else dump.result_set.exclude(plugin__name="banners.Banners")
        )
        for result in tasks_list:
            result.result = RESULT_STATUS_DISABLED
            result.save()
        send_to_ws(dump, message="Missing symbols all plugin are disabled", color=4)
