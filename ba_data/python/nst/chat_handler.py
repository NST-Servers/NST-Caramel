"""Chat message handler."""
from __future__ import annotations
from typing import TYPE_CHECKING

import random
import re

import bascenev1 as bs

if TYPE_CHECKING:
    from typing import Any

def handle_chat_message(msg: str, client_id: int) -> str | None:
    """Intercept/filter chat messages.

    Called for all chat messages while hosting.
    Messages originating from the host will have clientID -1.
    Should filter and return the string to be displayed, or return None
    to ignore the message.
    """
    # Ignore empty messages.
    if len(msg) < 1:
        return None

    # Host only checks
    if bs.get_foreground_host_session() is not None:
        activity = bs.get_foreground_host_activity()
        if activity:
            with activity.context:
                in_game_chat(msg, client_id)

    if bs.get_foreground_host_session() is not None:
        with bs.get_foreground_host_session().context:
            bs.getsound('message').play()

    return msg

def in_game_chat(msg: str, client_id: int) -> None:
    """Creates a text node at the client's spaz."""
    activity = bs.getactivity()
    # Ignore if we're paused
    if activity.globalsnode.paused:
        return

    # Get players matching the client id
    player = next((p for p in activity.players if p.sessionplayer.inputdevice.client_id == client_id), None)

    if player is None:
        return

    spaz = player.actor
    # Don't do our silly shenanigans if we're unable to
    if spaz is None or not spaz.node:
        return
    if not spaz.is_alive():
        return

    # Store our message temporarily so we can
    # display long spliced chat messages
    if not hasattr(spaz, 'chatmessage'):
        spaz.chatmessage = ''
    spaz.chatmessage += f'{msg}\n'

    def reset_chat():
        """Resets spaz's chat message variable."""
        spaz.chatmessage = ''

    # Do it!
    spaz.chatnode = ChatMessagePopupText(
        spaz.chatmessage,
        spaz,
    )
    # Allow for some message stacking
    spaz.chatnodetime = bs.Timer(3, reset_chat)

    # Wave if we greet people or say goodbye
    if msg.lower().startswith((
        # Saying hello
        'hi',
        'hello',
        'howdy',
        'yo',
        'hewwo',
        'hey',
        'hi',
        'heya',
        'heyah',
        'greetings',
        'hai',
        'sup',
        'wassup',
        'wazzup',
        'what\'s up',
        # Saying goodbye
        'bye',
        'goodbye',
        'farewell',
        'see ya',
        'see you',
        'see y\'all',
        'see y\'all later',
        'cya',
        'babye',
        'bbye',
        'ciao',
        'gbye',
        'good night',
        'goodnight',
        'gn',
        'arrivederci roma',
        'adios',
        'have fun'
    )):
        spaz.node.handlemessage(random.choice(['celebrate_l', 'celebrate_r']), 500)

class ChatMessagePopupText(bs.Actor):
    """Text that pops up above a position to denote something special.

    category: Gameplay Classes
    """

    def __init__(
        self,
        text: str,
        spaz: Any,
    ):
        """Instantiate with given values.

        random_offset is the amount of random offset from the provided position
        that will be applied. This can help multiple achievements from
        overlapping too much.
        """
        super().__init__()

        self.spaz = spaz
        self.text = text

        if not hasattr(spaz.node, 'position'):
            return

        pos = spaz.node.position
        color = ([x*1.5 for x in bs.normalized_color(spaz.node.color)])

        if len(color) == 3:
            color = (color[0], color[1], color[2], 1.0)
        pos = (
            pos[0] + (random.uniform(-0.1, 0.1)),
            pos[1],
            pos[2] + (random.uniform(-0.1, 0.1)),
        )

        # Create a node mimicking our spaz's position.
        mathnode = bs.newnode(
            'math',
            owner=spaz.node,
            attrs={
                'input1': (0, 0.9, 0),
                'operation': 'add',
            },
        )
        spaz.node.connectattr(
            'torso_position', mathnode, 'input2'
        )
        # Node!
        self.node = bs.newnode(
            'text',
            owner=mathnode,
            attrs={
                'text': text,
                'in_world': True,
                'shadow': 1.0,
                'flatness': 1.0,
                'h_align': 'center',
                'v_align': 'bottom',
                'maxwidth': 400,
            },
            delegate=self,
        )
        # Connect the node to our spaz.
        mathnode.connectattr('output', self.node, 'position')

        lifespan = 2.5+(0.018*len(text))

        # Scaling
        bs.animate(
            self.node,
            'scale',
            {
                0: 0.0,
                0.11: 0.020 * 0.7 * 1.5,
                0.16: 0.013 * 0.7 * 1.5,
                0.25: 0.014 * 0.7 * 1.5,
            },
        )

        # Fading
        self._combine = bs.newnode(
            'combine',
            owner=self.node,
            attrs={
                'input0': color[0],
                'input1': color[1],
                'input2': color[2],
                'size': 4,
            },
        )
        for i in range(4):
            bs.animate(
                self._combine,
                'input' + str(i),
                {
                    0.13: color[i],
                    0.18: 4.0 * color[i],
                    0.22: color[i],
                },
            )
        bs.animate(
            self._combine,
            'input3',
            {
                0: 0,
                0.1: color[3],
                lifespan - 0.8: color[3],
                lifespan: 0,
            },
        )
        self._combine.connectattr('output', self.node, 'color')

        # Play a sound depending on how AGGRESSIVE our message is.
        shout = get_shouting(text) > 0.75
        spaz.node.handlemessage(
            'scream_sound' if shout
            else 'jump_sound'
        )
        # Celebrate depending on if we shout or not
        if shout:
            spaz.node.handlemessage('celebrate', (lifespan*1000)*0.15)

        # Death.
        self._die_timer = bs.Timer(
            lifespan, bs.WeakCall(self.handlemessage, bs.DieMessage())
        )

    def handlemessage(self, msg: Any) -> Any:
        """Handle death."""
        assert not self.expired
        if isinstance(msg, bs.DieMessage):
            if self.node:
                self.node.delete()
        else:
            super().handlemessage(msg)

def get_shouting(msg: str) -> float:
    """Compare uppercase characters and return the lower/upper ratio.

    Args:
        msg (str): The text you want to check.

    Returns:
        float: The uppercase-to-lowercase ratio in a scale of 1.
    """
    text = re.sub(r'[^a-zA-Z]', '', msg)

    total: int = len(text)
    if total < 3:
        return 0
    cap: int = 0

    for ltr in text:
        if ltr.isupper():
            cap += 1

    return cap / total