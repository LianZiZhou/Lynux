import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    property var shell

    title: app.s.nav_system

    FormCard.FormHeader {
        title: app.s.system_language_input
    }
    FormCard.FormCard {
        FormCard.FormComboBoxDelegate {
            id: languageBox
            text: app.s.language
            description: app.s.system_language_desc
            model: app.languages
            textRole: "name"
            valueRole: "code"
            Component.onCompleted: currentIndex = app.languages.findIndex(item => item.code === app.language)
            onActivated: app.setLanguage(currentValue)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "input-keyboard"
            text: app.s.system_input
            description: app.s.system_input_desc
            onClicked: app.openInputSettings()
        }
    }

    FormCard.FormHeader {
        title: app.s.system_connections
    }
    FormCard.FormCard {
        FormCard.FormButtonDelegate {
            icon.name: "network-wireless"
            text: app.s.system_network
            description: app.s.system_network_desc
            onClicked: app.openNetwork()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "system-file-manager"
            text: app.s.system_files
            description: app.s.system_files_desc
            onClicked: app.openFolder("")
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "partitionmanager"
            text: app.s.system_partitions
            description: app.s.system_partitions_desc
            onClicked: app.openPartitionManager()
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "preferences-system"
            text: app.s.system_settings
            description: app.s.system_settings_desc
            onClicked: app.openSystemSettings()
        }
    }

    FormCard.FormHeader {
        title: app.s.system_window
    }
    FormCard.FormCard {
        FormCard.FormSwitchDelegate {
            text: app.s.system_autostart
            checked: app.autostart
            onToggled: app.setAutostart(checked)
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "help-contents"
            text: app.s.home_guide
            description: app.s.home_guide_desc
            onClicked: app.openGuide()
        }
    }

    FormCard.FormHeader {
        title: app.s.system_about
    }
    FormCard.FormCard {
        FormCard.FormTextDelegate {
            text: app.s.system_version
            description: app.version ? "Lynux " + app.version : "Lynux"
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormTextDelegate {
            text: app.s.system_timezone
            description: app.s.system_timezone_desc
        }
        FormCard.FormDelegateSeparator {}
        FormCard.FormButtonDelegate {
            icon.name: "internet-services"
            text: app.s.system_source
            description: app.project
            onClicked: app.openUrl(app.project)
        }
    }
}
