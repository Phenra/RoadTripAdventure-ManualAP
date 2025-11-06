# Object classes from AP core, to represent an entire MultiWorld and this individual World that's part of it
from worlds.AutoWorld import World
from BaseClasses import MultiWorld, CollectionState, Item, Location, LocationProgressType

# Object classes from Manual -- extending AP core -- representing items and locations that are used in generation
from ..Items import ManualItem
from ..Locations import ManualLocation

# Raw JSON data from the Manual apworld, respectively:
#          data/game.json, data/items.json, data/locations.json, data/regions.json
#
from ..Data import game_table, item_table, location_table, region_table

# These helper methods allow you to determine if an option has been set, or what its value is, for any player in the multiworld
from ..Helpers import is_option_enabled, get_option_value, format_state_prog_items_key, ProgItemsCat

# calling logging.info("message") anywhere below in this file will output the message to both console and log file
import logging

########################################################################################
## Order of method calls when the world generates:
##    1. create_regions - Creates regions and locations
##    2. create_items - Creates the item pool
##    3. set_rules - Creates rules for accessing regions and locations
##    4. generate_basic - Runs any post item pool options, like place item/category
##    5. pre_fill - Creates the victory location
##
## The create_item method is used by plando and start_inventory settings to create an item from an item name.
## The fill_slot_data method will be used to send data to the Manual client for later use, like deathlink.
########################################################################################



# Use this function to change the valid filler items to be created to replace item links or starting items.
# Default value is the `filler_item_name` from game.json
def hook_get_filler_item_name(world: World, multiworld: MultiWorld, player: int) -> str | bool:
    return False

# Called before regions and locations are created. Not clear why you'd want this, but it's here. Victory location is included, but Victory event is not placed yet.
def before_create_regions(world: World, multiworld: MultiWorld, player: int):
    # Modifying the regionMap directly is likely *not* the best... but if Stamps mode is enabled, we really need to 
    #   set the requires for locations and regions based on the alternate 'stampMode' settings in the YAML.
    # To my (limited) knowledge, if we were to try to modify the location/region requires after the initial ones are 
    #   set (i.e. using the after_set_rules hook), we would need to parse the stampMode strings from the YAML into
    #   dictionaries. The code for that string parsing is local to the set_rules function... and I also don't think
    #   copying that entire function here is the best idea, either.
    # I'm probably missing another option, but since I don't see it at the moment, I'm editing regionMap here.
    from ..Regions import regionMap

    # Many items, locations, and regions in Road Trip AP depend on whether the player is using Decorations or Stamps for area unlocks.
    # If Stamps mode, swap requirements for locations and regions that relied on decorations to use their stampMode settings instead.

    if get_option_value(multiworld, player, "area_unlock_mode") == 1: # Stamp mode 
        for location in location_table:
            if "stampModeRegion" in location:
                location["region"] = location["stampModeRegion"]
            if "stampModeRequires" in location:
                location["requires"] = location["stampModeRequires"]

        for region in region_table: 
            if "stampModeRequires" in region_table[region]:
                regionMap[region]["requires"] = region_table[region]["stampModeRequires"]
                region_table[region]["requires"] = region_table[region]["stampModeRequires"] # Update in both, just in case region_table is used later

# Called after regions and locations are created, in case you want to see or modify that information. Victory location is included.
def after_create_regions(world: World, multiworld: MultiWorld, player: int):
    # Use this hook to remove locations from the world
    locationNamesToRemove: list[str] = [] # List of location names

    # If Decorations mode, and 'Remove Double Up Stamps' is enabled, remove any locations in the 'Double-Up' category.
    # If Decorations mode, and 'Remove Double Up Stamps' is not enabled, remove any locations in the 'Combined' category.
    # If Stamps mode, always remove all locations with category 'Combined'.

    if get_option_value(multiworld, player, "area_unlock_mode") == 0: # Decorations mode      
        for location in location_table:
            if "category" in location:
                if is_option_enabled(multiworld, player, "remove_double_up_stamps") and "Double-Up" in location["category"]:
                    # Remove item
                    locationNamesToRemove.append(location["name"])

                    # Add name of item to combined stamp
                    if "doubleUpStamp" in location:
                        doubleUpStampName = location["doubleUpStamp"]

                        # Find the stamp in location_table that matches the one listed in the 'doubleUpStamp' property
                        stamp = [loc for loc in location_table if loc['name'] == doubleUpStampName]
                        if len(stamp) == 0:
                            raise Exception(f"Error in locations.json: Supplied doubleUpStamp for location f{location['name']} does not exist.")
                        else:
                            stamp = stamp[0]
                        
                        nameToAdd = location["name"]
                        stamp['name'] += f" / {nameToAdd}"
                    else:
                        raise Exception (f"Error in locations.json: All locations in Double-Up category should have a 'doubleUpStamp' property. This one does not: {location['name']}")
        
    elif get_option_value(multiworld, player, "area_unlock_mode") == 1: # Stamp mode     
        for location in location_table:
            if "category" in location and "Combined" in location["category"]:
                locationNamesToRemove.append(location["name"])

    else:
        raise Exception("Area Unlock Mode is not Decorations or Stamps, please fix your YAML.")

    # Define location categories where we want to potentially force a good item to be placed
    raceCategories = ["Races - C-Rank", "Races - B-Rank", "Races - A-Rank", "Races - Other"]
    minigameCategories = ["Challenge"]

    # Pull the percent chances (set in the YAML) for races and certain minigames to have good items forced there
    percentChanceRace = get_option_value(multiworld, player, "prioritize_good_rewards_for_races")
    percentChanceMinigame = get_option_value(multiworld, player, "prioritize_good_rewards_for_minigames")

    # Define function to handle forcing a good item to be placed at the passed location on successful roll
    def rollForForceGoodItem(location, percentChance, random):
        x = random.randint(1, 100)
        if x <= percentChance:
            # Using 'location.item_rule' for this caused generation to fail when using Stamps mode and no additional progressive
            #    item tracks (possibly due to being too restrictive?)
            # Setting the location as priority seems to force item fill for that location to be handled prior to other
            #    locations, which fixes this issue.
            # However, we can only force the placement of a Progression item using this - this can't place a Useful item.

            #location.item_rule = lambda item: item.advancement or item.useful or item.skip_in_prog_balancing
            location.progress_type = LocationProgressType.PRIORITY

    for region in multiworld.regions:
        if region.player == player:
            for location in list(region.locations):
                # Remove all locations in the 'locationsNamesToRemove' list (default Manual behavior)
                if location.name in locationNamesToRemove:
                    region.locations.remove(location)
                else:
                    # For each location in the world, roll for a chance of forcing a good item to be there if it has one 
                    #     of the earlier-defined categories. 
                    # Categories do not appear to be stored in the location object from the multiworld, so we need to
                    #     cross-reference location_table.
                    locationTableObj = None
                    for obj in location_table: # Find the corresponding object in location_table so we can get the location's category
                        if obj['name'] == location.name:
                            locationTableObj = obj
                            break
                    if locationTableObj is not None:
                        # If 'prioritize_good_rewards_for_races' is set: For each race location, roll for a chance 
                        #     to force a good item to be placed there.
                        if any(category in locationTableObj['category'] for category in raceCategories):
                            rollForForceGoodItem(location, percentChanceRace, world.random)
                        # If 'prioritize_good_rewards_for_minigames' is set: For each mini-game stamp labelled with 
                        #     the 'Challenge' category, roll for a chance to force a good item to be placed there.
                        elif any(category in locationTableObj['category'] for category in minigameCategories):
                            rollForForceGoodItem(location, percentChanceMinigame, world.random)

# This hook allows you to access the item names & counts before the items are created. Use this to increase/decrease the amount of a specific item in the pool
# Valid item_config key/values:
# {"Item Name": 5} <- This will create qty 5 items using all the default settings
# {"Item Name": {"useful": 7}} <- This will create qty 7 items and force them to be classified as useful
# {"Item Name": {"progression": 2, "useful": 1}} <- This will create 3 items, with 2 classified as progression and 1 as useful
# {"Item Name": {0b0110: 5}} <- If you know the special flag for the item classes, you can also define non-standard options. This setup
#       will create 5 items that are the "useful trap" class
# {"Item Name": {ItemClassification.useful: 5}} <- You can also use the classification directly
def before_create_items_all(item_config: dict[str, int|dict], world: World, multiworld: MultiWorld, player: int) -> dict[str, int|dict]:
    
    unlockMode = get_option_value(multiworld, player, "area_unlock_mode")
    progressivePartOption = get_option_value(multiworld, player, "additional_progressive_part_tracks")

    def removeAllItemsInCategories(item_table, categories):
        if isinstance(categories, str): # Convert to list of length 1 if string is passed
            categories = [categories]
        for item in item_table:
            if "category" in item and any(category in item["category"] for category in categories):
                item_config[item["name"]] = 0

    # If Decorations mode, remove all Stamp items, and remove any items specific to Stamp mode (e.g. the filler versions of the Area Unlock 
    #     items and the two decorations for Peach Town).    
    if unlockMode == 0: # Decorations mode
        removeAllItemsInCategories(item_table, ["Stamp Progression Only", "Stamps"])

        # Dynamically changing an item's category in a hook does not seem to work, so I defined two copies of the area keys: one for Decorations mode
        #     (which are actually used as keys, and are Progression), and one for Stamps mode (which are not used as keys, so just Filler).
        #     
        # Defining two items with the same name is not allowed, so I added "(Key)" to the names of the Area Unlock items.
        #     However, this could lead players to believe they need to type (for example) "Mini-Tower (Key)" in the script in order to receive the item in-game,
        #     so I want to remove it from the name during generation to prevent confusion.
        #
        # Previously, there was only one copy for each of these items, and I simply changed all of the items in the Area Unlock category to Filler.
        #     However, this results in those items still appearing under "Area Unlocks" in the Manual client, which would be confusing in Stamps mode,
        #     where they are not area unlocks.

        # ISSUE: Renaming is causing issues with generation, since it's expecting the old names. Commenting this out.
        # for i in item_table:
        #     if " (Key)" in i['name']:
        #         value = item_config.pop(i['name'])
        #         i['name'] = i['name'].replace(" (Key)", "")
        #         item_config[i['name']] = value

    # If Stamps mode, remove all 'Area Unlock' items
    elif unlockMode == 1: # Stamp mode
        removeAllItemsInCategories(item_table, ["Area Unlocks"])

    else:
        raise Exception("Area Unlock Mode is not Decorations or Stamps, please fix your YAML.")
    
    # If 'additional_progressive_part_tracks' is less than 2, remove all items in the 'Upgrade Set 3' category.
    if progressivePartOption < 2:
        removeAllItemsInCategories(item_table, "Upgrade Set 3")
    # If 'additional_progressive_part_tracks' is less than 1, also remove all items in the 'Upgrade Set 2' category.
    if progressivePartOption < 1:
        removeAllItemsInCategories(item_table, "Upgrade Set 2")

    return item_config

# The item pool before starting items are processed, in case you want to see the raw item pool at that stage
def before_create_items_starting(item_pool: list, world: World, multiworld: MultiWorld, player: int) -> list:
    return item_pool

# The item pool after starting items are processed but before filler is added, in case you want to see the raw item pool at that stage
def before_create_items_filler(item_pool: list, world: World, multiworld: MultiWorld, player: int) -> list:
    from BaseClasses import ItemClassification

    # Use this hook to remove items from the item pool
    itemNamesToRemove: list[str] = [] # List of item names

    # If item count is greater than location count, remove filler in a specific category order (stopping mid-category once enough have been removed):
    #     Garage Wallpapers, Garage Decorations, Bodies, Sticker, Wheels, Meters

    # Items in the item pool don't seem to retain their category data (categories might be a Manual-specific concept?), so a function
    #     like this is needed.
    def isItemFromPoolInCategory(item : Item, item_table : list, category : str) -> bool:
        for i in item_table:
            if item.name == i['name']:
                return True if category in i['category'] else False

    # Copying several lines and overall structure from 'adjust_filler_items' in the manual world's __init__.py
    extras = len(item_pool) - len(multiworld.get_unfilled_locations(player))

    if extras > 0:
        fillers = [item for item in item_pool if item.classification == ItemClassification.filler]

        wallpaperNames = [item.name for item in fillers if isItemFromPoolInCategory(item, item_table, "Garage Wallpaper")] # Assuming every item has a name
        decorationNames = [item.name for item in fillers if isItemFromPoolInCategory(item, item_table, "Garage Decoration")] 
        bodyNames = [item.name for item in fillers if isItemFromPoolInCategory(item, item_table, "Body")]
        stickerNames = ["Sticker"]
        wheelNames = [item.name for item in fillers if isItemFromPoolInCategory(item, item_table, "Wheel")]
        meterNames = [item.name for item in fillers if isItemFromPoolInCategory(item, item_table, "Meter")]

        categories = [wallpaperNames, decorationNames, bodyNames, stickerNames, wheelNames, meterNames]

        for category in categories:
            world.random.shuffle(category)
            numToRemove = len(category) if len(category) < extras else extras

            for i in range (0, numToRemove):
                itemNamesToRemove.append(category[i])

            extras -= len(category)

    # Because multiple copies of an item can exist, you need to add an item name
    # to the list multiple times if you want to remove multiple copies of it.
    for itemName in itemNamesToRemove:
        item = next(i for i in item_pool if i.name == itemName)
        item_pool.remove(item)

    return item_pool

    # Some other useful hook options:

    ## Place an item at a specific location
    # location = next(l for l in multiworld.get_unfilled_locations(player=player) if l.name == "Location Name")
    # item_to_place = next(i for i in item_pool if i.name == "Item Name")
    # location.place_locked_item(item_to_place)
    # item_pool.remove(item_to_place)

# The complete item pool prior to being set for generation is provided here, in case you want to make changes to it
def after_create_items(item_pool: list, world: World, multiworld: MultiWorld, player: int) -> list:
    return item_pool

# Called before rules for accessing regions and locations are created. Not clear why you'd want this, but it's here.
def before_set_rules(world: World, multiworld: MultiWorld, player: int):
    pass

# Called after rules for accessing regions and locations are created, in case you want to see or modify that information.
def after_set_rules(world: World, multiworld: MultiWorld, player: int):
    # Use this hook to modify the access rules for a given location

    def Example_Rule(state: CollectionState) -> bool:
        # Calculated rules take a CollectionState object and return a boolean
        # True if the player can access the location
        # CollectionState is defined in BaseClasses
        return True

    ## Common functions:
    # location = world.get_location(location_name, player)
    # location.access_rule = Example_Rule

    ## Combine rules:
    # old_rule = location.access_rule
    # location.access_rule = lambda state: old_rule(state) and Example_Rule(state)
    # OR
    # location.access_rule = lambda state: old_rule(state) or Example_Rule(state)

# The item name to create is provided before the item is created, in case you want to make changes to it
def before_create_item(item_name: str, world: World, multiworld: MultiWorld, player: int) -> str:
    return item_name

# The item that was created is provided after creation, in case you want to modify the item
def after_create_item(item: ManualItem, world: World, multiworld: MultiWorld, player: int) -> ManualItem:
    return item

# This method is run towards the end of pre-generation, before the place_item options have been handled and before AP generation occurs
def before_generate_basic(world: World, multiworld: MultiWorld, player: int):
    pass

# This method is run at the very end of pre-generation, once the place_item options have been handled and before AP generation occurs
def after_generate_basic(world: World, multiworld: MultiWorld, player: int):
    pass

# This method is run every time an item is added to the state, can be used to modify the value of an item.
# IMPORTANT! Any changes made in this hook must be cancelled/undone in after_remove_item
def after_collect_item(world: World, state: CollectionState, Changed: bool, item: Item):
    # the following let you add to the Potato Item Value count
    # if item.name == "Cooked Potato":
    #     state.prog_items[item.player][format_state_prog_items_key(ProgItemsCat.VALUE, "Potato")] += 1
    pass

# This method is run every time an item is removed from the state, can be used to modify the value of an item.
# IMPORTANT! Any changes made in this hook must be first done in after_collect_item
def after_remove_item(world: World, state: CollectionState, Changed: bool, item: Item):
    # the following let you undo the addition to the Potato Item Value count
    # if item.name == "Cooked Potato":
    #     state.prog_items[item.player][format_state_prog_items_key(ProgItemsCat.VALUE, "Potato")] -= 1
    pass


# This is called before slot data is set and provides an empty dict ({}), in case you want to modify it before Manual does
def before_fill_slot_data(slot_data: dict, world: World, multiworld: MultiWorld, player: int) -> dict:
    return slot_data

# This is called after slot data is set and provides the slot data at the time, in case you want to check and modify it after Manual is done with it
def after_fill_slot_data(slot_data: dict, world: World, multiworld: MultiWorld, player: int) -> dict:
    return slot_data

# This is called right at the end, in case you want to write stuff to the spoiler log
def before_write_spoiler(world: World, multiworld: MultiWorld, spoiler_handle) -> None:
    pass

# This is called when you want to add information to the hint text
def before_extend_hint_information(hint_data: dict[int, dict[int, str]], world: World, multiworld: MultiWorld, player: int) -> None:
    # Send location hints for all Shop Purchase locations at the beginning of the game so the player can tell what they're buying.
    def isLocationInCategory(location : Location, location_table : list, category : str) -> bool:
        for i in location_table:
            if location.name == i['name']:
                return True if category in i['category'] else False
    
    for location in multiworld.get_locations(player):
        if isLocationInCategory(location, location_table, "Shop Purchases"):
            world.options.start_location_hints.value.add(location.name)

    ### Example way to use this hook:
    # if player not in hint_data:
    #     hint_data.update({player: {}})
    # for location in multiworld.get_locations(player):
    #     if not location.address:
    #         continue
    #
    #     use this section to calculate the hint string
    #
    #     hint_data[player][location.address] = hint_string

    pass

def after_extend_hint_information(hint_data: dict[int, dict[int, str]], world: World, multiworld: MultiWorld, player: int) -> None:
    pass
