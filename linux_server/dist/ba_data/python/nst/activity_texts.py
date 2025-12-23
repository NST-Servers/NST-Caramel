"""Activity text actors."""

from __future__ import annotations

from typing import TYPE_CHECKING
import random

import bascenev1 as bs

if TYPE_CHECKING:
    from typing import Any

# In seconds
INFO_DURATION = 15
NOTIF_DURATION = 8
NOTIF_INTERVAL = 120

class InfoText(bs.Actor):
    """Text shown at the start of activity explaining server mechanics."""

    def __init__(self):
        super().__init__()
        text = (
            "Gameplay changes:\n"
            "- Quick-Turn\n"
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
                'position': (15, -515),
                'scale': 0.6,
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
        bs.animate(self.node, 'opacity', {INFO_DURATION - 2: 0.8, INFO_DURATION: 0})
        bs.timer(INFO_DURATION, self.node.delete)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            if self.node:
                self.node.delete()
        return super().handlemessage(msg)


class WatermarkText(bs.Actor):
    """Text shown in the bottom left corner."""

    def __init__(self):
        super().__init__()
        self.node = bs.newnode(
            'text',
            attrs={
                'v_attach': 'bottom',
                'h_attach': 'right',
                'h_align': 'right',
                'position': (-25, -90),
                'scale': 0.35,
                'big': True,
                'text': 'NST Caramel',
                'color': (0.851, 0.408, 0),
                'shadow': 0.5,
                'flatness': 1.0,
            },
        )

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
        interval: float = NOTIF_INTERVAL,
    ):
        super().__init__()
        if messages is None:
            messages = [
                "Consider donating at buymeacoffee.com/sok05",
                "Hold *GRAB* to wave!",
                "When waving, you can hold *PUNCH* to celebrate!",
                "You can freeze powerups with Ice Bomb!"
            ]

        self._messages = list(messages)
        random.shuffle(self._messages)
        self._interval = interval
        self._index = 0

        self.node = bs.newnode(
            'text',
            attrs={
                'v_attach': 'top',
                'h_attach': 'center',
                'h_align': 'center',
                'position': (0, -100),
                'scale': 0.8,
                'color': (1, 1, 1,),
                'shadow': 0.5,
                'flatness': 1.0,
                'maxwidth': 600,
                'opacity': 0.0,
            },
        )

        self._timer = bs.Timer(
            interval, bs.WeakCallStrict(self._update), repeat=True
        )
        self._update()

    def _update(self) -> None:
        if not self.node:
            return

        if not self._messages:
            return

        text = self._messages[self._index]
        self.node.text = text

        # Set initial state (invisible and up)
        self.node.opacity = 0.0
        self.node.position = (0, -50)

        show_duration = NOTIF_DURATION
        if show_duration > self._interval:
            show_duration = self._interval - 0.5

        # Animate in and out
        bs.animate(
            self.node,
            'opacity',
            {
                0.0: 0,
                0.5: 0.9,
                show_duration - 2: 0.9,
                show_duration: 0,
            },
        )
        bs.animate_array(self.node, 'position', 2, {
            0: (0, -50),
            0.1: (0, -55),
            0.2: (0, -68),
            0.3: (0, -82),
            0.4: (0, -95),
            0.5: (0, -100),
        })

        self._index += 1
        if self._index >= len(self._messages):
            self._index = 0
            random.shuffle(self._messages)

    def add_message(self, message: str | bs.Lstr) -> None:
        """Add a message to the rotation."""
        self._messages.append(message)

    def handlemessage(self, msg: Any) -> Any:
        if isinstance(msg, bs.DieMessage):
            if self.node:
                self.node.delete()
        return super().handlemessage(msg)
