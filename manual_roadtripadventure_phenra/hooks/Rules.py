from typing import Optional
from worlds.AutoWorld import World
from ..Helpers import clamp, get_items_with_value, get_option_value
from BaseClasses import MultiWorld, CollectionState

import re

def cityAccessCount(multiworld: MultiWorld, state: CollectionState, player: int, count: int):
    if get_option_value(multiworld, player, "area_unlock_mode") == 0: # Decorations mode
        return [
            state.can_reach_region("Peach Town", player),
            state.can_reach_region("Fuji City", player),
            state.can_reach_region("Sandpolis", player),
            state.can_reach_region("Chestnut Canyon", player),
            state.can_reach_region("Mushroom Road", player),
            state.can_reach_region("White Mountain", player),
            state.can_reach_region("Papaya Island", player),

            # Do not count Cloud Hill - this is used only for testing access to Q Coins for Coine's rewards
            # state.can_reach_region("Cloud Hill", player)
        ].count(True) >= count

    elif get_option_value(multiworld, player, "area_unlock_mode") == 1: # Stamp mode
        return state.count("Stamp", player) >= 5 * (count - 1)
    
    else:
        raise Exception("Area Unlock Mode is not Decorations or Stamps, please fix your YAML.")


# Example functions from Manual below:
# -------------------------------------------
# Sometimes you have a requirement that is just too messy or repetitive to write out with boolean logic.
# Define a function here, and you can use it in a requires string with {function_name()}.
def overfishedAnywhere(world: World, state: CollectionState, player: int):
    """Has the player collected all fish from any fishing log?"""
    for cat, items in world.item_name_groups:
        if cat.endswith("Fishing Log") and state.has_all(items, player):
            return True
    return False

# You can also pass an argument to your function, like {function_name(15)}
# Note that all arguments are strings, so you'll need to convert them to ints if you want to do math.
def anyClassLevel(state: CollectionState, player: int, level: str):
    """Has the player reached the given level in any class?"""
    for item in ["Figher Level", "Black Belt Level", "Thief Level", "Red Mage Level", "White Mage Level", "Black Mage Level"]:
        if state.count(item, player) >= int(level):
            return True
    return False

# You can also return a string from your function, and it will be evaluated as a requires string.
def requiresMelee():
    """Returns a requires string that checks if the player has unlocked the tank."""
    return "|Figher Level:15| or |Black Belt Level:15| or |Thief Level:15|"
