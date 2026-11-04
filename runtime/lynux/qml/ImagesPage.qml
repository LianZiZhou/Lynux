import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Dialogs as Dialogs
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    property var shell
    property string path: ""
    property var result: null
    property bool hashing: false

    title: app.s.nav_images
    Component.onCompleted: app.refreshIsos()

    Connections {
        target: app
        function onFinished(kind, outcome) {
            if (kind === "inspect") {
                page.hashing = false
                if (outcome.ok)
                    page.result = outcome
                else
                    page.shell.notify(page.shell.errorText(outcome))
            } else if ((kind === "mount_iso" || kind === "unmount_iso") && !outcome.ok) {
                page.shell.notify(page.shell.errorText(outcome))
            }
        }
    }

    FormCard.FormHeader {
        title: app.s.images_check
    }
    FormCard.FormCard {
        FormCard.FormButtonDelegate {
            icon.name: "document-open"
            text: page.path ? app.fileName(page.path) : app.s.images_choose
            description: page.path ? page.path : app.s.images_choose_desc
            onClicked: fileDialog.open()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextFieldDelegate {
            id: expected
            label: app.s.images_expected
            placeholderText: app.s.images_expected_hint
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "document-preview"
            text: app.s.images_verify
            enabled: page.path !== "" && !page.hashing
            onClicked: {
                page.result = null
                page.hashing = true
                app.inspectIso(page.path, expected.text)
            }
        }
        FormCard.AbstractFormDelegate {
            visible: page.hashing
            background: null
            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing

                QQC2.BusyIndicator {
                    running: page.hashing
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }
                QQC2.Label {
                    Layout.fillWidth: true
                    text: app.s.images_hashing
                    wrapMode: Text.Wrap
                }
            }
        }
        FormCard.FormDelegateSeparator {
            visible: !!page.result
        }
        ActionRow {
            visible: !!page.result
            iconName: "document-preview"
            text: app.s.images_result
            description: page.result ? page.result.sha256 : ""

            QQC2.Button {
                text: app.s.images_copy
                icon.name: "edit-copy"
                onClicked: app.copyText(page.result.sha256)
            }
        }
        FormCard.FormTextDelegate {
            visible: !!page.result && page.result.match !== null && page.result.match !== undefined
            icon.name: page.result && page.result.match ? "emblem-success" : "emblem-error"
            text: page.result && page.result.match ? app.s.images_match : app.s.images_mismatch
            textItem.color: page.result && page.result.match ? Kirigami.Theme.positiveTextColor
                                                              : Kirigami.Theme.negativeTextColor
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "media-mount"
            text: app.s.images_mount
            description: app.s.images_mount_desc
            enabled: page.path !== ""
            onClicked: app.mountIso(page.path)
        }
    }

    FormCard.FormHeader {
        visible: app.isos.length > 0
        title: app.s.images_mounted
    }
    FormCard.FormCard {
        visible: app.isos.length > 0

        Repeater {
            model: app.isos

            delegate: ColumnLayout {
                id: mountedRow

                required property var modelData
                required property int index

                Layout.fillWidth: true
                spacing: 0

                FormCard.FormDelegateSeparator {
                    visible: mountedRow.index > 0
                }
                ActionRow {
                    iconName: "media-optical"
                    text: app.fileName(mountedRow.modelData.source)
                    description: mountedRow.modelData.mount

                    QQC2.Button {
                        text: app.s.open_folder
                        icon.name: "document-open-folder"
                        onClicked: app.openFolder(mountedRow.modelData.mount)
                    }
                    QQC2.Button {
                        text: app.s.images_unmount
                        icon.name: "media-eject"
                        onClicked: app.unmountIso(mountedRow.modelData.id)
                    }
                }
            }
        }
    }

    FormCard.FormSectionText {
        text: app.s.images_note
    }

    Dialogs.FileDialog {
        id: fileDialog
        title: app.s.images_choose
        nameFilters: ["ISO (*.iso)", "* (*)"]
        currentFolder: "file:///run/media"
        onAccepted: {
            page.path = app.localPath(selectedFile.toString())
            page.result = null
        }
    }
}
