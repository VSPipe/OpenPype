from Qt import QtWidgets, QtCore, QtGui
from Qt.QtCore import Qt
from avalon import style
from avalon.api import AvalonMongoDB
from pype.tools.settings.settings.widgets.base import ProjectListWidget
from pype.modules import ModulesManager

from pype.lib import PypeLogger
log = PypeLogger().get_logger("SyncServer")


class SyncServerWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SyncServerWindow, self).__init__(parent)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.setStyleSheet(style.load_stylesheet())
        self.resize(1400, 800)

        body = QtWidgets.QWidget()
        footer = QtWidgets.QWidget()
        footer.setFixedHeight(20)

        container = QtWidgets.QWidget()
        projects = SyncProjectListWidget(self)
        repres = SyncRepresentationWidget(self)

        container_layout = QtWidgets.QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        split = QtWidgets.QSplitter()
        split.addWidget(projects)
        split.addWidget(repres)
        split.setSizes([180, 950, 200])
        container_layout.addWidget(split)

        container.setLayout(container_layout)

        self.dbcon = AvalonMongoDB()
        self.dbcon.install()
        self.dbcon.Session["AVALON_PROJECT"] = None

        # Project
        self.combo_projects = QtWidgets.QComboBox()

        body_layout = QtWidgets.QHBoxLayout(body)
        body_layout.addWidget(container)
        body_layout.setContentsMargins(0, 0, 0, 0)

        message = QtWidgets.QLabel()
        message.hide()

        footer_layout = QtWidgets.QVBoxLayout(footer)
        footer_layout.addWidget(message)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(body)
        layout.addWidget(footer)

        self.setLayout(body_layout)
        self.setWindowTitle("Sync Server")


class SyncProjectListWidget(ProjectListWidget):

    def validate_context_change(self):
        return True

    def refresh(self):
        selected_project = None
        for index in self.project_list.selectedIndexes():
            selected_project = index.data(QtCore.Qt.DisplayRole)
            break

        model = self.project_list.model()
        model.clear()
        items = []
        manager = ModulesManager()
        sync_server = manager.modules_by_name["sync_server"]

        for project_name in sync_server.get_synced_presets().keys():
            items.append(project_name)

        print("!!!! items:: {}".format(items))
        sync_server.log.debug("ld !!!! items:: {}".format(items))
        for item in items:
            model.appendRow(QtGui.QStandardItem(item))

        # self.select_project(selected_project)

        self.current_project = self.project_list.currentIndex().data(
            QtCore.Qt.DisplayRole
        )


class SyncRepresentationWidget(QtWidgets.QWidget):
    active_changed = QtCore.Signal()    # active index changed

    default_widths = (
        ("asset", 130),
        ("subset", 190),
        ("version", 30),
        ("representation", 30),
        ("created_dt", 120),
        ("sync_dt", 85),
        ("local_site", 80),
        ("remote_site", 60),
        ("priority", 55),
        ("state", 50)
    )

    def __init__(self, parent=None):
        super(SyncRepresentationWidget, self).__init__(parent)

        filter = QtWidgets.QLineEdit()
        filter.setPlaceholderText("Filter subsets..")

        top_bar_layout = QtWidgets.QHBoxLayout()
        top_bar_layout.addWidget(filter)

        # TODO ? TreeViewSpinner

        table_view = QtWidgets.QTableView()
        headers = [item[0] for item in self.default_widths]
        log.debug("!!! headers:: {}".format(headers))
        model = SyncRepresentationModel(headers)
        table_view.setModel(model)
        table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        table_view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        table_view.setSortingEnabled(True)
        table_view.setAlternatingRowColors(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top_bar_layout)
        layout.addWidget(table_view)

        table_view.doubleClicked.connect(self._doubleClicked)

    def _doubleClicked(self, index):
        log.debug("doubleclicked {}:{}".format(index.row(), index.column))
        detail_window = SyncServerDetailWindow(index)
        detail_window.open()


class SyncRepresentationModel(QtCore.QAbstractTableModel):
    PAGE_SIZE = 30
    DEFAULT_SORT = {
        "context.asset": 1,
        "context.subset": 1,
        "context.version": 1,
    }
    SORT_BY_COLUMN = [
        "context.asset",            # asset
        "context.subset",           # subset
        "context.version",          # version
        "context.representation",   # representation
        "_id",                      # local created_dt
        "order.created_dt",   # remote created_dt
        "files.sites.name",  # TEMP # local progress
        "files.sites.name",   # TEMP# remote progress
        "context.asset",            # priority
        "context.asset"             # state
    ]
    DEFAULT_QUERY = {
        "type": "representation",
    }

    numberPopulated = QtCore.Signal(int)

    def __init__(self, header, project=None):
        super(SyncRepresentationModel, self).__init__()
        self._header = header
        self._data = []
        self._project = project
        self._rec_loaded = 0
        self._buffer = []  # stash one page worth of records (actually cursor)

        self._initialized = False

        self.dbcon = AvalonMongoDB()
        self.dbcon.install()
        self.dbcon.Session["AVALON_PROJECT"] = self._project or 'petr_test'  # TEMP

        manager = ModulesManager()
        sync_server = manager.modules_by_name["sync_server"]
        # TODO think about admin mode
        # this is for regular user, always only single local and single remote
        self.local_site, self.remote_site = \
            sync_server.get_sites_for_project('petr_test')

        self.query = self.DEFAULT_QUERY

        self.projection = {
            "context.subset": 1,
            "context.asset": 1,
            "context.version": 1,
            "context.representation": 1,
            "files": 1
        }

        self.sort = self.DEFAULT_SORT

        self.query = self.get_default_query()
        self.default_query = list(self.get_default_query())
        log.debug("!!! init query: {}".format(self.query))
        representations = self.dbcon.aggregate(self.query)
        self.refresh(representations)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._header[section])

            # if orientation == Qt.Vertical:
            #     return str(self._data[section])

    def refresh(self, representations):
        self.beginResetModel()
        self._data = []
        self._rec_loaded = 0
        log.debug("!!! refresh sort {}".format(self.sort))

        self._add_page_records(self.local_site, self.remote_site,
                               representations)
        self.endResetModel()

    def _add_page_records(self, local_site, remote_site, representations):
        log.debug("!!! representations:: {}".format(representations))
        #log.debug("!!! representations:: {}".format(len(representations)))
        for repre in representations:
            context = repre.get("context")
            # log.debug("!!! context:: {}".format(context))
            # log.debug("!!! repre:: {}".format(repre))
            # log.debug("!!! repre:: {}".format(type(repre)))
            created = {}
            # log.debug("!!! files:: {}".format(repre.get("files", [])))
            # log.debug("!!! files:: {}".format(type(repre.get("files", []))))
            files = repre.get("files", [])
            if isinstance(files, dict):  # aggregate returns dictionary
                files = [files]
            for file in files:
                # log.debug("!!! file:: {}".format(file))
                # log.debug("!!! file:: {}".format(type(file)))
                sites = file.get("sites")
                # log.debug("!!! sites:: {}".format(sites))
                for site in sites:
                    # log.debug("!!! site:: {}".format(site))
                    # log.debug("!!! site:: {}".format(type(site)))
                    if not isinstance(site, dict):
                        # log.debug("Obsolete site {} for {}".format(
                        #     site, repre.get("_id")))
                        continue

                    if site.get("name") != local_site and \
                            site.get("name") != remote_site:
                        continue

                    if not created.get(site.get("name")):
                        created[site.get("name")] = []

                    created[site.get("name")]. \
                        append(site.get("created_dt"))

            # log.debug("!!! created:: {}".format(created))
            # log.debug("!!! remote_site:: {}".format(remote_site))
            local_created = ''
            if all(created.get(local_site, [None])):
                local_created = min(created[local_site])
            # log.debug("!!! local_created:: {}".format(local_created))
            remote_created = ''
            if all(created.get(remote_site, [None])):
                remote_created = min(created[remote_site])

            item = [
                context.get("asset"),
                context.get("subset"),
                "v{:0>3d}".format(context.get("version", 1)),
                context.get("representation"),
                str(local_created),
                str(remote_created),
                local_site,
                remote_site,
                1,
                0
            ]
            self._data.append(item)
            self._rec_loaded += 1

    def canFetchMore(self, index):
        """
            Check if there are more records than currently loaded
        """
        log.debug("!!! canFetchMore _rec_loaded:: {}".format(self._rec_loaded))
        # 'skip' might be suboptimal when representation hits 500k+
        # self._buffer = list(self.dbcon.aggregate(self.query))
        # log.debug("!!! self._buffer.count():: {}".format(len(self._buffer)))
        # return len(self._buffer) > self._rec_loaded
        return False

    def fetchMore(self, index):
        """
            Add more record to model.

            Called when 'canFetchMore' returns true, which means there are
            more records in DB than loaded.
            'self._buffer' is used to stash cursor to limit requery
        """
        log.debug("fetchMore")
        # cursor.count() returns always total number, not only skipped + limit
        remainder = self._buffer.count() - self._rec_loaded
        items_to_fetch = min(self.PAGE_SIZE, remainder)
        self.beginInsertRows(index,
                             self._rec_loaded,
                             self._rec_loaded + items_to_fetch - 1)

        self._add_page_records(self.local_site, self.remote_site, self._buffer)

        self.endInsertRows()

        self.numberPopulated.emit(items_to_fetch)  # ??

    def sort(self, index, order):
        log.debug("!!! sort {} {}".format(index, order))
        log.debug("!!! orig query {}".format(self.query))
        self._rec_loaded = 0
        # limit unwanted first re-sorting by view
        if index < 0:
            return

        if order == 0:
            order = 1
        else:
            order = -1

        if index < 5:
            self.sort = {self.SORT_BY_COLUMN[index]: order}
            self.query = self.get_default_query()
        elif index == 5:
            self.sort = {self.SORT_BY_COLUMN[index]: order}
            self.query = [
                {"$match": {
                    "type": "representation",
                    "files.sites": {
                        "$elemMatch": {
                            "name": self.remote_site,
                            "created_dt": {"$exists": 1}
                        },
                    }
                }},
                {"$unwind": "$files"},
                {"$addFields": {
                    "order": {
                        "$filter": {
                          "input": "$files.sites",
                          "as": "p",
                          "cond": {"$eq": ["$$p.name", self.remote_site]}
                        }
                    }
                }},
                {"$sort": self.sort},
                {"$limit": self.PAGE_SIZE},
                {"$skip": self._rec_loaded},
                {"$project": self.projection}
            ]
        log.debug("!!! sort {}".format(self.sort))
        log.debug("!!! query {}".format(self.query))
        representations = self.dbcon.aggregate(self.query)
        self.refresh(representations)

    def get_default_query(self):
        return [
            {"$match": {
                "type": "representation",
            }},
            {"$sort": self.sort},
            {"$limit": self.PAGE_SIZE},
            {"$skip": self._rec_loaded},
            {"$project": self.projection}
        ]


class SyncServerDetailWindow(QtWidgets.QDialog):
    def __init__(self, index, parent=None):
        super(SyncServerDetailWindow, self).__init__(parent)
        log.debug("SyncServerDetailWindow {}:{}".format(index.row(), index.column))
        self.setWindowFlags(QtCore.Qt.Window)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.setStyleSheet(style.load_stylesheet())
        self.resize(1000, 400)

        body = QtWidgets.QWidget()
        footer = QtWidgets.QWidget()
        footer.setFixedHeight(20)

        self.dbcon = AvalonMongoDB()
        self.dbcon.install()
        self.dbcon.Session["AVALON_PROJECT"] = None

        container = SyncRepresentationDetailWidget(self)
        body_layout = QtWidgets.QHBoxLayout(body)
        body_layout.addWidget(container)
        body_layout.setContentsMargins(0, 0, 0, 0)

        message = QtWidgets.QLabel()
        message.hide()

        footer_layout = QtWidgets.QVBoxLayout(footer)
        footer_layout.addWidget(message)
        footer_layout.setContentsMargins(0, 0, 0, 0)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(body)
        layout.addWidget(footer)

        self.setLayout(body_layout)
        self.setWindowTitle("Sync Representation Detail")


class SyncRepresentationDetailWidget(QtWidgets.QWidget):
    active_changed = QtCore.Signal()    # active index changed

    default_widths = (
        ("file", 230),
        ("created_dt", 120),
        ("sync_dt", 85),
        ("local_site", 80),
        ("remote_site", 60),
        ("priority", 55),
        ("state", 50)
    )

    def __init__(self, parent=None):
        super(SyncRepresentationDetailWidget, self).__init__(parent)

        filter = QtWidgets.QLineEdit()
        filter.setPlaceholderText("Filter subsets..")

        top_bar_layout = QtWidgets.QHBoxLayout()
        top_bar_layout.addWidget(filter)

        table_view = QtWidgets.QTableView()
        headers = [item[0] for item in self.default_widths]
        log.debug("!!! SyncRepresentationDetailWidget headers:: {}".format(headers))

        model = SyncRepresentationModel(headers)
        table_view.setModel(model)
        table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        table_view.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        table_view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        table_view.setSortingEnabled(True)
        table_view.setAlternatingRowColors(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top_bar_layout)
        layout.addWidget(table_view)

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._header[section])

            # if orientation == Qt.Vertical:
            #     return str(self._data[section])

