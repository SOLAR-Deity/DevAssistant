"""Small presentation-only widgets shared by pages."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


def page_layout(parent: QWidget, title: str, subtitle: str = '') -> QVBoxLayout:
    content = QVBoxLayout(parent)
    content.setContentsMargins(26, 22, 26, 20)
    content.setSpacing(13)
    heading = QLabel(title)
    heading.setObjectName('pageTitle')
    content.addWidget(heading)
    if subtitle:
        desc = QLabel(subtitle)
        desc.setWordWrap(True)
        desc.setObjectName('mutedLabel')
        content.addWidget(desc)
    return content
