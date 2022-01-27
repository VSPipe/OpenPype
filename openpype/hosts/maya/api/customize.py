"""A set of commands that install overrides to Maya's UI"""

import os
import logging

from functools import partial

import maya.cmds as mc
import maya.mel as mel

from avalon.maya import pipeline
from openpype.api import resources
from openpype.tools.utils import host_tools


log = logging.getLogger(__name__)

COMPONENT_MASK_ORIGINAL = {}


def override_component_mask_commands():
    """Override component mask ctrl+click behavior.

    This implements special behavior for Maya's component
    mask menu items where a ctrl+click will instantly make
    it an isolated behavior disabling all others.

    Tested in Maya 2016 and 2018

    """
    log.info("Installing override_component_mask_commands..")

    # Get all object mask buttons
    buttons = mc.formLayout("objectMaskIcons",
                            query=True,
                            childArray=True)
    # Skip the triangle list item
    buttons = [btn for btn in buttons if btn != "objPickMenuLayout"]

    def on_changed_callback(raw_command, state):
        """New callback"""

        # If "control" is held force the toggled one to on and
        # toggle the others based on whether any of the buttons
        # was remaining active after the toggle, if not then
        # enable all
        if mc.getModifiers() == 4:  # = CTRL
            state = True
            active = [mc.iconTextCheckBox(btn, query=True, value=True) for btn
                      in buttons]
            if any(active):
                mc.selectType(allObjects=False)
            else:
                mc.selectType(allObjects=True)

        # Replace #1 with the current button state
        cmd = raw_command.replace(" #1", " {}".format(int(state)))
        mel.eval(cmd)

    for btn in buttons:

        # Store a reference to the original command so that if
        # we rerun this override command it doesn't recursively
        # try to implement the fix. (This also allows us to
        # "uninstall" the behavior later)
        if btn not in COMPONENT_MASK_ORIGINAL:
            original = mc.iconTextCheckBox(btn, query=True, cc=True)
            COMPONENT_MASK_ORIGINAL[btn] = original

        # Assign the special callback
        original = COMPONENT_MASK_ORIGINAL[btn]
        new_fn = partial(on_changed_callback, original)
        mc.iconTextCheckBox(btn, edit=True, cc=new_fn)


def override_toolbox_ui():
    """Add custom buttons in Toolbox as replacement for Maya web help icon."""
    icons = resources.get_resource("icons")

    # Ensure the maya web icon on toolbox exists
    web_button = "ToolBox|MainToolboxLayout|mayaWebButton"
    if not mc.iconTextButton(web_button, query=True, exists=True):
        return

    mc.iconTextButton(web_button, edit=True, visible=False)

    # real = 32, but 36 with padding - according to toolbox mel script
    icon_size = 36
    parent = web_button.rsplit("|", 1)[0]

    # Ensure the parent is a formLayout
    if not mc.objectTypeUI(parent) == "formLayout":
        return

    # Create our controls
    controls = []

    controls.append(
        mc.iconTextButton(
            "pype_toolbox_lookmanager",
            annotation="Look Manager",
            label="Look Manager",
            image=os.path.join(icons, "lookmanager.png"),
            command=host_tools.show_look_assigner,
            width=icon_size,
            height=icon_size,
            parent=parent
        )
    )

    controls.append(
        mc.iconTextButton(
            "pype_toolbox_workfiles",
            annotation="Work Files",
            label="Work Files",
            image=os.path.join(icons, "workfiles.png"),
            command=lambda: host_tools.show_workfiles(
                parent=pipeline._parent
            ),
            width=icon_size,
            height=icon_size,
            parent=parent
        )
    )

    controls.append(
        mc.iconTextButton(
            "pype_toolbox_loader",
            annotation="Loader",
            label="Loader",
            image=os.path.join(icons, "loader.png"),
            command=lambda: host_tools.show_loader(
                parent=pipeline._parent, use_context=True
            ),
            width=icon_size,
            height=icon_size,
            parent=parent
        )
    )

    controls.append(
        mc.iconTextButton(
            "pype_toolbox_manager",
            annotation="Inventory",
            label="Inventory",
            image=os.path.join(icons, "inventory.png"),
            command=lambda: host_tools.show_scene_inventory(
                parent=pipeline._parent
            ),
            width=icon_size,
            height=icon_size,
            parent=parent
        )
    )

    # Add the buttons on the bottom and stack
    # them above each other with side padding
    controls.reverse()
    for i, control in enumerate(controls):
        previous = controls[i - 1] if i > 0 else web_button

        mc.formLayout(parent, edit=True,
                      attachControl=[control, "bottom", 0, previous],
                      attachForm=([control, "left", 1],
                                  [control, "right", 1]))
