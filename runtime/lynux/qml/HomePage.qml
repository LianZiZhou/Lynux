import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    property var shell
    readonly property var active: app.status.active

    title: app.s.nav_home

    ColumnLayout {
        Layout.fillWidth: true
        Layout.topMargin: Kirigami.Units.gridUnit * 2
        Layout.bottomMargin: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
            source: "lynux"
            fallback: "utilities-terminal"
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Kirigami.Units.gridUnit * 5
            implicitHeight: implicitWidth
        }
        Kirigami.Heading {
            text: app.s.home_title
            level: 1
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
        }
        QQC2.Label {
            text: app.s.home_subtitle
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 28
            Layout.alignment: Qt.AlignHCenter
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            opacity: 0.8
        }
    }

    FormCard.FormHeader {
        title: app.s.home_status
    }
    FormCard.FormCard {
        FormCard.FormButtonDelegate {
            icon.name: page.active ? "object-unlocked" : "edit-clear-history"
            text: page.active ? app.s.home_saved : app.s.home_temporary
            description: page.active ? app.s.home_saved_desc.arg(page.active.container) : app.s.home_temporary_desc
            onClicked: page.shell.currentPage = "storage"
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: app.online ? "network-connect" : "network-disconnect"
            text: app.online ? app.s.home_online : app.s.home_offline
            description: app.online ? "" : app.s.home_offline_desc
            onClicked: app.openNetwork()
        }
    }

    FormCard.FormHeader {
        title: app.s.home_start
    }
    FormCard.FormCard {
        FormCard.FormButtonDelegate {
            icon.name: "utilities-terminal"
            text: app.s.home_tools
            description: app.s.home_tools_desc
            onClicked: page.shell.currentPage = "tools"
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "document-encrypt"
            text: app.s.home_storage
            description: app.s.home_storage_desc
            onClicked: page.shell.currentPage = "storage"
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "media-optical"
            text: app.s.home_images
            description: app.s.home_images_desc
            onClicked: page.shell.currentPage = "images"
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "help-contents"
            text: app.s.home_guide
            description: app.s.home_guide_desc
            onClicked: app.openGuide()
        }
    }

    FormCard.FormSectionText {
        text: app.s.home_footer
    }
}
