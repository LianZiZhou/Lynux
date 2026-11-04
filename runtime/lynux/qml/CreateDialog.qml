import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: dialog

    property var shell
    property bool running: false
    property string stage: ""
    property real fraction: -1
    property string error: ""

    readonly property real gib: 1024 * 1024 * 1024
    readonly property var drives: (app.status.locations || []).filter(item => item.writable || item.ventoy)
    readonly property var drive: drives[driveBox.currentIndex] || null
    readonly property int maxSize: {
        if (!drive)
            return 0
        let size = Math.floor((drive.free - 512 * 1024 * 1024) / gib)
        if (drive.fat)
            size = Math.min(size, 3)
        return Math.max(size, 0)
    }
    readonly property bool nameOk: /^([^\/]+\/)?[^\/]+\.luks$/.test(fileField.text)
                                   && !fileField.text.split("/").some(part => part === "." || part === "..")
    readonly property bool passwordOk: password.text.length >= 8 && password.text === repeat.text
    readonly property bool canCreate: !running && !!drive && drive.writable && maxSize >= 1 && nameOk
                                      && passwordOk && sizeBox.value <= maxSize

    function start() {
        error = ""
        running = true
        stage = "allocate"
        fraction = 0
        app.createContainer(drive.mount + "/" + fileField.text, sizeBox.value, password.text)
    }

    title: app.s.create_title
    preferredWidth: Kirigami.Units.gridUnit * 32
    padding: Kirigami.Units.largeSpacing
    showCloseButton: !running
    closePolicy: running ? QQC2.Popup.NoAutoClose : QQC2.Popup.CloseOnEscape
    standardButtons: Kirigami.Dialog.NoButton
    customFooterActions: [
        Kirigami.Action {
            text: app.s.create_button
            icon.name: "document-encrypt"
            enabled: dialog.canCreate
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
        repeat.text = ""
        sizeBox.value = Math.min(8, Math.max(1, maxSize))
        app.refresh()
    }
    onClosed: {
        password.text = ""
        repeat.text = ""
    }

    Connections {
        target: app
        function onProgress(kind, stage, fraction) {
            if (kind !== "create")
                return
            dialog.stage = stage
            dialog.fraction = fraction
        }
        function onFinished(kind, result) {
            if (kind !== "create")
                return
            dialog.running = false
            if (result.ok) {
                dialog.close()
                dialog.shell.notify(app.s.create_done)
            } else {
                dialog.error = dialog.shell.errorText(result)
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
            type: Kirigami.MessageType.Warning
            text: app.s.create_no_drive
            visible: dialog.drives.length === 0
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            type: Kirigami.MessageType.Information
            text: app.s.ventoy_readonly_desc
            visible: !!dialog.drive && !dialog.drive.writable
            actions: [
                Kirigami.Action {
                    text: app.s.ventoy_make_writable
                    icon.name: "document-edit"
                    onTriggered: app.mountVentoy()
                }
            ]
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true
            enabled: !dialog.running

            QQC2.ComboBox {
                id: driveBox
                Kirigami.FormData.label: app.s.create_drive
                Layout.fillWidth: true
                enabled: dialog.drives.length > 0
                model: dialog.drives.map(item => (item.label || item.mount) + " — "
                    + (item.writable ? app.s.create_free.arg(dialog.shell.bytes(item.free)) : app.s.create_readonly))
            }
            QQC2.TextField {
                id: fileField
                Kirigami.FormData.label: app.s.create_file
                Layout.fillWidth: true
                text: "Lynux/state.luks"
            }
            QQC2.Label {
                Layout.fillWidth: true
                Layout.maximumWidth: Kirigami.Units.gridUnit * 28
                text: dialog.nameOk ? app.s.create_file_hint : app.s.create_file_bad
                color: dialog.nameOk ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.negativeTextColor
                font: Kirigami.Theme.smallFont
                wrapMode: Text.Wrap
            }
            QQC2.SpinBox {
                id: sizeBox
                Kirigami.FormData.label: app.s.create_size
                from: 1
                to: Math.max(1, dialog.maxSize)
                value: 8
                editable: true
                textFromValue: (value, locale) => value + " GiB"
                valueFromText: (text, locale) => parseInt(text) || 1
            }
            QQC2.Label {
                Layout.fillWidth: true
                Layout.maximumWidth: Kirigami.Units.gridUnit * 28
                visible: !!dialog.drive && dialog.drive.writable
                text: dialog.drive && dialog.drive.fat ? app.s.create_fat_hint
                                                         : app.s.create_size_hint.arg(dialog.maxSize + " GiB")
                color: Kirigami.Theme.disabledTextColor
                font: Kirigami.Theme.smallFont
                wrapMode: Text.Wrap
            }
            Kirigami.PasswordField {
                id: password
                placeholderText: ""
                Kirigami.FormData.label: app.s.password
                Layout.fillWidth: true
            }
            Kirigami.PasswordField {
                id: repeat
                placeholderText: ""
                Kirigami.FormData.label: app.s.password_repeat
                Layout.fillWidth: true
                onAccepted: if (dialog.canCreate) dialog.start()
            }
            QQC2.Label {
                Layout.fillWidth: true
                Layout.maximumWidth: Kirigami.Units.gridUnit * 28
                text: password.text.length > 0 && password.text.length < 8 ? app.s.password_short
                    : (repeat.text.length > 0 && repeat.text !== password.text ? app.s.password_mismatch : "")
                visible: text !== ""
                color: Kirigami.Theme.negativeTextColor
                font: Kirigami.Theme.smallFont
                wrapMode: Text.Wrap
            }
        }

        QQC2.Label {
            Layout.fillWidth: true

            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            text: app.s.create_warning + " " + app.s.create_import
            wrapMode: Text.Wrap
            opacity: 0.8
        }

        ColumnLayout {
            visible: dialog.running
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            QQC2.ProgressBar {
                Layout.fillWidth: true
                from: 0
                to: 1
                value: Math.max(dialog.fraction, 0)
                indeterminate: dialog.stage !== "allocate" || dialog.fraction < 0
            }
            QQC2.Label {
                text: dialog.stage === "allocate" ? app.s.stage_allocate.arg(Math.round(Math.max(dialog.fraction, 0) * 100))
                                                  : (app.s["stage_" + dialog.stage] || "")
            }
        }
    }
}
