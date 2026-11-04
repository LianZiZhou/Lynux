import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

FormCard.FormCardPage {
    id: page

    property var shell
    // Neutral Breeze accent colours, one per tool, so the list is easy to scan.
    readonly property var badges: ({
        codex: { label: "Cx", color: "#1d99f3" },
        claude: { label: "Cl", color: "#f67400" },
        kimi: { label: "Ki", color: "#9b59b6" },
        dsh: { label: "DS", color: "#16a085" },
        opencode: { label: "OC", color: "#27ae60" }
    })

    title: app.s.nav_tools

    FormCard.FormHeader {
        title: app.s.tools_header
    }
    FormCard.FormCard {
        Repeater {
            model: app.tools

            delegate: ColumnLayout {
                id: row

                required property var modelData
                required property int index

                Layout.fillWidth: true
                spacing: 0

                FormCard.FormDelegateSeparator {
                    visible: row.index > 0
                }
                FormCard.FormButtonDelegate {
                    Layout.fillWidth: true
                    text: row.modelData.name
                    description: {
                        const about = app.s["tool_" + row.modelData.id]
                        const version = row.modelData.version
                        return version ? about + " · " + app.s.tools_version.arg(version) : about
                    }
                    leading: Rectangle {
                        implicitWidth: Kirigami.Units.iconSizes.medium
                        implicitHeight: implicitWidth
                        radius: Kirigami.Units.cornerRadius
                        color: (page.badges[row.modelData.id] || { color: Kirigami.Theme.highlightColor }).color

                        QQC2.Label {
                            anchors.centerIn: parent
                            text: (page.badges[row.modelData.id] || { label: "?" }).label
                            color: "white"
                            font.bold: true
                        }
                    }
                    onClicked: app.launchTool(row.modelData.id)
                }
            }
        }
    }
    FormCard.FormSectionText {
        text: app.s.tools_note
    }

    FormCard.FormHeader {
        title: app.s.tools_admin
    }
    FormCard.FormCard {
        FormCard.FormButtonDelegate {
            icon.name: "utilities-terminal"
            text: app.s.tools_root
            description: app.s.tools_root_desc
            onClicked: app.launchTool("shell")
        }
    }
}
