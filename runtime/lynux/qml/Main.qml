import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.delegates as Delegates

Kirigami.ApplicationWindow {
    id: root

    property string currentPage: "home"
    readonly property var pageList: [
        { id: "home", icon: "go-home", key: "nav_home" },
        { id: "tools", icon: "utilities-terminal", key: "nav_tools" },
        { id: "storage", icon: "document-encrypt", key: "nav_storage" },
        { id: "images", icon: "media-optical", key: "nav_images" },
        { id: "system", icon: "preferences-system", key: "nav_system" }
    ]

    title: "Lynux"
    width: Kirigami.Units.gridUnit * 52
    height: Kirigami.Units.gridUnit * 38
    minimumWidth: Kirigami.Units.gridUnit * 36
    minimumHeight: Kirigami.Units.gridUnit * 26

    function bytes(value) {
        if (value === undefined || value === null)
            return ""
        const units = ["B", "KiB", "MiB", "GiB", "TiB"]
        let index = 0
        let amount = value
        while (amount >= 1024 && index < units.length - 1) {
            amount /= 1024
            index++
        }
        const text = index === 0 ? String(amount) : amount.toFixed(amount < 10 ? 1 : 0)
        return text + " " + units[index]
    }

    function errorText(result) {
        const template = app.s["err_" + result.code]
        if (template === undefined)
            return app.s.err_generic.arg(result.message || result.code)
        return template.arg(result.path || "")
    }

    function notify(text) {
        showPassiveNotification(text, "long")
    }

    function loadPage() {
        const pages = { home: homePage, tools: toolsPage, storage: storagePage, images: imagesPage,
                        system: systemPage }
        // Create the page with a parent ourselves: Kirigami would create it parentless, which Qt
        // warns about. Pages we create are not owned by the stack, so destroy the old ones here.
        const old = pageStack.items.slice()
        pageStack.clear()
        for (const item of old)
            item.destroy()
        const page = pages[currentPage].createObject(pageStack, { shell: root, objectName: "currentPage-" + currentPage })
        pageStack.push(page)
    }

    Component { id: homePage; HomePage {} }
    Component { id: toolsPage; ToolsPage {} }
    Component { id: storagePage; StoragePage {} }
    Component { id: imagesPage; ImagesPage {} }
    Component { id: systemPage; SystemPage {} }

    onCurrentPageChanged: loadPage()
    Component.onCompleted: loadPage()

    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.NoNavigationButtons
    pageStack.columnView.columnResizeMode: Kirigami.ColumnView.SingleColumn

    globalDrawer: Kirigami.OverlayDrawer {
        id: drawer

        edge: Qt.application.layoutDirection === Qt.RightToLeft ? Qt.RightEdge : Qt.LeftEdge
        modal: false
        drawerOpen: true
        handleVisible: false
        width: Kirigami.Units.gridUnit * 13
        leftPadding: 0
        rightPadding: 0
        topPadding: 0
        bottomPadding: 0

        Kirigami.Theme.colorSet: Kirigami.Theme.View
        Kirigami.Theme.inherit: false

        contentItem: ColumnLayout {
            spacing: 0

            QQC2.ToolBar {
                Layout.fillWidth: true
                Layout.preferredHeight: root.pageStack.globalToolBar.preferredHeight

                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Icon {
                        source: "lynux"
                        fallback: "utilities-terminal"
                        Layout.leftMargin: Kirigami.Units.smallSpacing
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: implicitWidth
                    }
                    Kirigami.Heading {
                        text: "Lynux"
                        level: 2
                        Layout.fillWidth: true
                    }
                }
            }

            ListView {
                id: navigation
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                clip: true
                model: root.pageList
                delegate: Delegates.RoundedItemDelegate {
                    required property var modelData
                    width: ListView.view.width
                    text: app.s[modelData.key]
                    icon.name: modelData.icon
                    highlighted: root.currentPage === modelData.id
                    onClicked: root.currentPage = modelData.id
                }
            }

            Kirigami.Separator {
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Icon {
                    source: "preferences-desktop-locale"
                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                    implicitHeight: implicitWidth
                }
                QQC2.ComboBox {
                    id: languageBox
                    Layout.fillWidth: true
                    model: app.languages
                    textRole: "name"
                    valueRole: "code"
                    Accessible.name: app.s.language
                    Component.onCompleted: currentIndex = indexOfValue(app.language)
                    onActivated: app.setLanguage(currentValue)

                    Connections {
                        target: app
                        function onStringsChanged() {
                            languageBox.currentIndex = languageBox.indexOfValue(app.language)
                        }
                    }
                }
            }
        }
    }

    Kirigami.PromptDialog {
        id: languageDialog

        property string failure: ""

        title: app.s.lang_changed_title
        subtitle: {
            const current = app.languages.find(item => item.code === app.language)
            const text = app.s.lang_changed_desc.arg(current ? current.name : app.language)
            return failure ? text + "\n\n" + app.s.lang_system_failed.arg(failure) : text
        }
        standardButtons: Kirigami.Dialog.NoButton
        customFooterActions: [
            Kirigami.Action {
                text: app.s.lang_logout
                icon.name: "system-log-out"
                onTriggered: {
                    languageDialog.close()
                    if (!app.logout())
                        root.notify(app.s.logout_failed)
                }
            },
            Kirigami.Action {
                text: app.s.lang_later
                icon.name: "dialog-cancel"
                onTriggered: languageDialog.close()
            }
        ]
    }

    Connections {
        target: app
        function onLanguageApplied(code, result) {
            languageDialog.failure = result.ok ? "" : (result.message || "")
            languageDialog.open()
        }
    }
}
