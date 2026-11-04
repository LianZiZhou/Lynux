import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    property var shell
    readonly property var active: app.status.active
    readonly property var ventoy: (app.status.ventoy || [])[0] || null
    readonly property var found: {
        const list = []
        for (const place of (app.status.locations || []))
            for (const item of place.containers)
                list.push(item)
        return list
    }

    title: app.s.nav_storage
    Component.onCompleted: app.refresh()

    Connections {
        target: app
        function onFinished(kind, result) {
            if (kind === "lock") {
                if (result.ok)
                    page.shell.notify(app.s.lock_done)
                else if (result.code === "busy" && result.holders && result.holders.length)
                    holdersDialog.show(result.holders, false)
                else if (result.code === "still_running")
                    holdersDialog.show(holdersDialog.groups.filter(group => result.remaining.includes(group.id)), true)
                else
                    page.shell.notify(page.shell.errorText(result))
            } else if (kind === "ventoy" && !result.ok) {
                page.shell.notify(page.shell.errorText(result))
            }
        }
    }

    FormCard.FormCard {
        Layout.topMargin: Kirigami.Units.gridUnit

        FormCard.AbstractFormDelegate {
            background: null
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    source: page.active ? "object-unlocked" : "object-locked"
                    Layout.alignment: Qt.AlignTop
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: implicitWidth
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Heading {
                        text: page.active ? app.s.storage_unlocked_title : app.s.storage_locked_title
                        level: 3
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                    }
                    QQC2.Label {
                        text: page.active ? page.active.container : app.s.storage_locked_desc
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        opacity: 0.8
                    }
                    QQC2.ProgressBar {
                        visible: !!page.active && page.active.total > 0
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.smallSpacing
                        from: 0
                        to: page.active ? page.active.total : 1
                        value: page.active ? page.active.used : 0
                    }
                    QQC2.Label {
                        visible: !!page.active && page.active.total > 0
                        text: page.active ? app.s.storage_usage.arg(page.shell.bytes(page.active.used))
                                                                 .arg(page.shell.bytes(page.active.total)) : ""
                        font: Kirigami.Theme.smallFont
                        opacity: 0.8
                    }
                }
            }
        }

        FormCard.FormDelegateSeparator {}

        ColumnLayout {
            visible: !page.active
            Layout.fillWidth: true
            spacing: 0

            FormCard.FormButtonDelegate {
                icon.name: "list-add"
                text: app.s.storage_create
                description: app.s.storage_create_desc
                enabled: !app.busy
                onClicked: createDialog.open()
            }
            FormCard.FormDelegateSeparator {}
            FormCard.FormButtonDelegate {
                icon.name: "object-unlocked"
                text: app.s.storage_unlock
                description: app.s.storage_unlock_desc
                enabled: !app.busy
                onClicked: unlockDialog.openFor("")
            }
        }

        ColumnLayout {
            visible: !!page.active
            Layout.fillWidth: true
            spacing: 0

            FormCard.FormButtonDelegate {
                icon.name: "folder-open"
                text: app.s.storage_open_workspace
                description: app.s.storage_open_workspace_desc
                onClicked: app.openFolder("/workspace")
            }
            FormCard.FormDelegateSeparator {}
            FormCard.FormButtonDelegate {
                icon.name: "object-locked"
                text: app.busy ? app.s.locking : app.s.storage_lock
                description: app.s.storage_lock_desc
                enabled: !app.busy
                onClicked: app.lock([], false)
            }
        }
    }

    FormCard.FormHeader {
        visible: !page.active && page.found.length > 0
        title: app.s.storage_found
    }
    FormCard.FormCard {
        visible: !page.active && page.found.length > 0

        Repeater {
            model: page.found

            delegate: ColumnLayout {
                id: foundRow

                required property var modelData
                required property int index

                Layout.fillWidth: true
                spacing: 0

                FormCard.FormDelegateSeparator {
                    visible: foundRow.index > 0
                }
                FormCard.FormButtonDelegate {
                    Layout.fillWidth: true
                    icon.name: "document-encrypted"
                    text: app.fileName(foundRow.modelData.path)
                    description: foundRow.modelData.path + " · " + page.shell.bytes(foundRow.modelData.size)
                    enabled: !app.busy
                    onClicked: unlockDialog.openFor(foundRow.modelData.path)
                }
            }
        }
    }

    FormCard.FormHeader {
        title: app.s.storage_ventoy
    }
    FormCard.FormCard {
        ActionRow {
            visible: !page.ventoy
            iconName: "drive-removable-media"
            text: app.s.ventoy_none
            description: app.s.ventoy_none_desc
        }
        ActionRow {
            visible: !!page.ventoy && !page.ventoy.mount
            iconName: "drive-removable-media"
            text: app.s.ventoy_unmounted
            description: page.ventoy ? page.ventoy.device : ""

            QQC2.Button {
                text: app.s.ventoy_mount
                icon.name: "media-mount"
                enabled: !app.busy
                onClicked: app.mountVentoy()
            }
        }
        ActionRow {
            visible: !!page.ventoy && !!page.ventoy.mount && !page.ventoy.writable
            iconName: "drive-removable-media"
            text: page.ventoy && page.ventoy.mount ? app.s.ventoy_readonly.arg(page.ventoy.mount) : ""
            description: app.s.ventoy_readonly_desc

            QQC2.Button {
                text: app.s.ventoy_make_writable
                icon.name: "document-edit"
                enabled: !app.busy
                onClicked: app.mountVentoy()
            }
        }
        ActionRow {
            visible: !!page.ventoy && !!page.ventoy.mount && !!page.ventoy.writable
            iconName: "drive-removable-media"
            text: page.ventoy && page.ventoy.mount ? app.s.ventoy_writable.arg(page.ventoy.mount) : ""

            QQC2.Button {
                text: app.s.open_folder
                icon.name: "document-open-folder"
                onClicked: app.openFolder(page.ventoy.mount)
            }
        }
    }

    FormCard.FormHeader {
        title: app.s.storage_saved
    }
    FormCard.FormCard {
        FormCard.FormTextDelegate {
            icon.name: "checkmark"
            text: app.s.saved_cli
            description: app.s.saved_cli_desc
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextDelegate {
            icon.name: "checkmark"
            text: app.s.saved_workspace
            description: app.s.saved_workspace_desc
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextDelegate {
            icon.name: "edit-clear-history"
            text: app.s.saved_not
            description: app.s.saved_not_desc
        }
    }

    CreateDialog {
        id: createDialog
        objectName: "createDialog"
        shell: page.shell
    }
    UnlockDialog {
        id: unlockDialog
        objectName: "unlockDialog"
        shell: page.shell
    }
    HoldersDialog {
        id: holdersDialog
        objectName: "holdersDialog"
        shell: page.shell
    }
}
