import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.Dialogs as Dialogs
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialog

    property var shell
    property bool running: false
    property string error: ""
    property string path: ""
    property string stage: ""

    readonly property var choices: {
        const list = []
        for (const place of (app.status.locations || []))
            for (const item of place.containers)
                list.push(item.path)
        if (path !== "" && !list.includes(path))
            list.push(path)
        return list
    }

    function openFor(file) {
        path = file || (choices.length ? choices[0] : "")
        open()
    }

    function start() {
        error = ""
        running = true
        stage = "open"
        app.unlockContainer(path, password.text)
    }

    title: app.s.unlock_title
    preferredWidth: Kirigami.Units.gridUnit * 30
    padding: Kirigami.Units.largeSpacing
    showCloseButton: !running
    closePolicy: running ? QQC2.Popup.NoAutoClose : QQC2.Popup.CloseOnEscape
    standardButtons: Kirigami.Dialog.NoButton
    customFooterActions: [
        Kirigami.Action {
            text: app.s.unlock_button
            icon.name: "object-unlocked"
            enabled: !dialog.running && dialog.path !== "" && password.text.length > 0
            onTriggered: dialog.start()
        },
        Kirigami.Action {
            text: app.s.cancel
            icon.name: "dialog-cancel"
            enabled: !dialog.running
            onTriggered: dialog.close()
        }
    ]

    onOpened: {
        error = ""
        running = false
        password.text = ""
        password.forceActiveFocus()
    }
    onClosed: password.text = ""

    Connections {
        target: app
        function onProgress(kind, stage, fraction) {
            if (kind === "unlock")
                dialog.stage = stage
        }
        function onFinished(kind, result) {
            if (kind !== "unlock")
                return
            dialog.running = false
            if (result.ok) {
                dialog.close()
                dialog.shell.notify(app.s.unlock_done)
                return
            }
            dialog.error = dialog.shell.errorText(result)
            if (result.code === "wrong_password") {
                password.selectAll()
                password.forceActiveFocus()
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true

            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            type: Kirigami.MessageType.Error
            text: dialog.error
            visible: text !== ""
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            type: Kirigami.MessageType.Information
            text: app.s.unlock_none
            visible: dialog.choices.length === 0
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true
            enabled: !dialog.running

            RowLayout {
                Kirigami.FormData.label: app.s.unlock_file
                Layout.fillWidth: true

                QQC2.ComboBox {
                    id: fileBox
                    Layout.fillWidth: true
                    Layout.minimumWidth: Kirigami.Units.gridUnit * 14
                    model: dialog.choices
                    enabled: dialog.choices.length > 0
                    currentIndex: dialog.choices.indexOf(dialog.path)
                    onActivated: dialog.path = currentText
                }
                QQC2.Button {
                    text: app.s.browse
                    icon.name: "document-open"
                    onClicked: fileDialog.open()
                }
            }
            Kirigami.PasswordField {
                id: password
                placeholderText: ""
                Kirigami.FormData.label: app.s.password
                Layout.fillWidth: true
                onAccepted: if (dialog.path !== "" && text.length > 0 && !dialog.running) dialog.start()
            }
        }

        RowLayout {
            visible: dialog.running
            spacing: Kirigami.Units.smallSpacing

            QQC2.BusyIndicator {
                running: dialog.running
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: implicitWidth
            }
            QQC2.Label {
                text: app.s["stage_" + dialog.stage] || ""
            }
        }
    }

    Dialogs.FileDialog {
        id: fileDialog
        title: app.s.unlock_title
        nameFilters: ["LUKS (*.luks)", "* (*)"]
        currentFolder: "file:///run/media"
        onAccepted: dialog.path = app.localPath(selectedFile.toString())
    }
}
