import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kirigamiaddons.formcard as FormCard

// A form row with an icon, two lines of text and buttons on the right. FormTextDelegate's
// `trailing` goes through a LayoutItemProxy that drops items appearing after the page loads,
// and these rows depend on status that arrives later.
FormCard.AbstractFormDelegate {
    id: row

    property string iconName: ""
    property string description: ""
    default property alias buttons: buttonRow.data

    focusPolicy: Qt.NoFocus
    background: null
    Layout.fillWidth: true

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
            visible: row.iconName !== ""
            source: row.iconName
            implicitWidth: Kirigami.Units.iconSizes.smallMedium
            implicitHeight: implicitWidth
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            QQC2.Label {
                Layout.fillWidth: true
                text: row.text
                wrapMode: Text.Wrap
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: text !== ""
                text: row.description
                color: Kirigami.Theme.disabledTextColor
                wrapMode: Text.Wrap
            }
        }
        RowLayout {
            id: buttonRow
            spacing: Kirigami.Units.smallSpacing
        }
    }
}
