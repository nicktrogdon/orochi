from uuid import UUID

from django.urls import path, register_converter

from orochi.website import views


class MultiindexConverter:
    regex = "[0-9a-f,-]{36,}"

    def valid_uuid(self, uuid):
        try:
            return UUID(uuid).version
        except ValueError:
            return None

    def to_python(self, value):
        return [x.strip() for x in value.split(",") if self.valid_uuid(x) is not None]

    def to_url(self, value):
        return value


class QueryConverter:
    regex = ".*"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(MultiindexConverter, "idxs")
register_converter(QueryConverter, "query")


app_name = "website"
urlpatterns = [
    path("", views.index, name="home"),
    path(
        "indexes/<idxs:indexes>/plugin/<str:plugin>/query/<query:query>",
        views.bookmarks,
        name="bookmarks",
    ),
    path(
        "indexes/<idxs:indexes>/plugin/<str:plugin>",
        views.bookmarks,
        name="bookmarks",
    ),
    path("create", views.create, name="index_create"),
    path("edit", views.edit, name="index_edit"),
    path("delete", views.delete, name="index_delete"),
    path("restart", views.restart, name="index_restart"),
    path("plugins", views.plugins, name="plugins"),
    path("analysis", views.analysis, name="analysis"),
    path("generate", views.generate, name="generate"),
    path("plugin", views.plugin, name="plugin"),
    path("parameters", views.parameters, name="parameters"),
    path("symbols", views.symbols, name="symbols"),
    path("export", views.export, name="export"),
    path("download_ext/<int:pk>", views.download_ext, name="download_ext"),
    # RUNNING TASKS
    path("dask/status", views.dask_status, name="dask_status"),
    # CHANGELOG
    path("changelog", views.changelog, name="changelog"),
    # EXTERNAL VIEW
    path("json_view/<int:pk>", views.json_view, name="json_view"),
    path("hex_view/<str:index>", views.hex_view, name="hex_view"),
    path("get_hex/<str:index>", views.get_hex, name="get_hex"),
    path("search_hex/<str:index>", views.search_hex, name="search_hex"),
    path(
        "diff_view/<str:index_a>/<str:index_b>/<str:plugin>",
        views.diff_view,
        name="diff_view",
    ),
    # USER PAGE
    path("enable_plugin", views.enable_plugin, name="enable_plugin"),
    path("star_bookmark", views.star_bookmark, name="star_bookmark"),
    path("install_plugin", views.install_plugin, name="install_plugin"),
    path("delete_bookmark", views.delete_bookmark, name="delete_bookmark"),
    path("edit_bookmark", views.edit_bookmark, name="edit_bookmark"),
    path("add_bookmark", views.add_bookmark, name="add_bookmark"),
    # ADMIN
    path("update_plugins", views.update_plugins, name="update_plugins"),
    path("update_symbols", views.update_symbols, name="update_symbols"),
    # RULES
    path("list_custom_rules", views.list_custom_rules, name="list_custom_rules"),
    path("publish_rules", views.publish_rules, name="publish_rules"),
    path("delete_rules", views.delete_rules, name="delete_rules"),
    path("make_rule_default", views.make_rule_default, name="make_rule_default"),
    path("download_rule/<int:pk>", views.download_rule, name="download_rule"),
]
