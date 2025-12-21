"""Activity text actors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import bascenev1 as bs

if TYPE_CHECKING:
    from typing import Any


class InfoText(bs.Actor):
    """Text shown at the start of activity explaining server mechanics."""

    def __init__(self):
        super().__init__()
        text = (
            "Gameplay changes:\n"
            "- No Punch Grab Spam\n"
            "- Gloves are slower, but stronger\n"
            "- Shields block a portion of damage\n"
            "- TNT has a visible respawn timer\n"
            "- Powerups last longer\n"
            "- And lots more tweaks!"
        )
        self.node = bs.newnode(
            'text',
            attrs={
                'v_attach': 'top',
                'h_attach': 'left',
                'h_align': 'left',
                'position': (15, -530),
                'scale': 0.7,
                'text': text,
                'color': (1, 1, 1, 1),
                'shadow': 0.5,
                'flatness': 1.0,
                'maxwidth': 400,
            },
        )

        # Fade in
        bs.animate(self.node, 'opacity', {0: 0, 1.0: 0.8})

        # Fade out and die
        bs.animate(self.node, 'opacity', {10.0: 0.8, 12.0: 0})
        bs.timer(12.0, self.node.delete)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            if self.node:
                self.node.delete()
        return super().handlemessage(msg)


class NotifText(bs.Actor):
    """Text shown at top center cycling through messages."""

    def __init__(
        self,
        messages: list[str | bs.Lstr] | None = None,
        interval: float = 60.0,
    ):
        super().__init__()
        if messages is None:
            messages = [
                "Consider donating at buymeacoffee.com/sok05"
            ]

        self._messages = messages
        self._interval = interval
        self._index = 0

        self.node = bs.newnode(
            'text',
            attrs={
                'v_attach': 'top',
                'h_attach': 'center',
                'h_align': 'center',
                'position': (0, -70),
                'scale': 1.0,
                'color': (1, 1, 1,),
                'shadow': 0.5,
                'flatness': 1.0,
                'maxwidth': 600,
                'opacity': 0.0,
            },
        )

        self._timer = bs.Timer(
            interval, bs.WeakCall(self._update), repeat=True
        )
        self._update()

    def _update(self) -> None:
        if not self.node:
            return

        if not self._messages:
            return

        text = self._messages[self._index]
        self.node.text = text

        # Show for 5 seconds
        show_duration = 5.0
        if show_duration > self._interval:
            show_duration = self._interval - 0.5

        bs.animate(
            self.node,
            'opacity',
            {
                0.0: 0,
                0.5: 0.8,
                show_duration: 0.8,
                show_duration + 0.5: 0,
            },
        )

        self._index = (self._index + 1) % len(self._messages)

    def add_message(self, message: str | bs.Lstr) -> None:
        """Add a message to the rotation."""
        self._messages.append(message)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            if self.node:
                self.node.delete()
        return super().handlemessage(msg)
