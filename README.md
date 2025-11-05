# Road Trip Adventure Manual Archipelago
This is a manual Archipelago implementation for the PS2 game Road Trip Adventure, built using the [ManualForArchipelago](https://github.com/ManualForArchipelago/Manual) project.

It's intended to be played using a fresh save file and updating your inventory using the included script, which also patches the game to prevent it from giving you items.

## Requirements
- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases)
- [PCSX2](https://pcsx2.net/downloads/) v2.0 or higher
- Python (Mac and Linux only)
- Road Trip NTSC disc image
    - MD5 checksum: e1598a1a2b1a296dbeae90927172d52a

## Randomizer Details
### Goal
- Win the race against against President Forest (Stamp 100)

### Area Unlock Modes: Decorations, or Stamps
- In Road Trip AP, you must unlock a city before you are allowed to interact with it in any way. This means you cannot enter any buildings, talk to anyone, or collect overworld items in a town until you unlock it. Peach Town and My City are unlocked by default.
    - The game is not currently patched to enforce this, so please go by the honor system!
    - The Temple Under the Sea is considered part of White Mountain.
- There are two YAML settings for what is required to unlock a town: **Decorations**, or **Stamps**.
- In Decorations mode, the garage decorations serve as area unlock keys. Each town has two decorations that serve as their key - obtaining either unlocks the town.
- In Stamps mode, your stamps become items in the multiworld, and you unlock the next town in linear sequence with every 5 stamps obtained.

| City | Decoration Unlock | Stamp Unlock |
| ---- | ---- | ---- |
| Peach Town | (Free) | (Free) |
| Fuji City | Gold Ornament / Policeman's Club | 5 stamps |
| My City | (Free) | (Free) |
| Sandpolis | Mini-Tower / Toy Gun | 10 stamps |
| Chestnut Canyon | Model Train / M. Carton's Painting | 15 stamps |
| Mushroom Road | Flower Pattern / Sky Pattern | 20 stamps |
| White Mountain | Christmas Tree / Arctic Pattern | 25 stamps |
| Papaya Island | Papaya Ukulele / UnbaboDoll | 30 stamps |
| Cloud Hill | God's Rod / Angel's Wings | 35 stamps |

### Items
- Progressive part upgrades
    - Tire upgrades are rewarded in order of their cost (e.g. Off-Road Tires are first, HG Racing Tires are last)
    - Two additional progressive upgrade tracks are also enabled by default (one for each of your teammates, although you can use these parts too, or even sell them)
- All items normally given to you via dialogue
- All overworld items (gemstones, the fountain pen, etc.)
- All license upgrades
- Stamps (only if the Area Unlock Mode is set to Stamps)
- Empty locations are filled with 500 money

### Locations
- Purchasing an item from the parts shop for the first time
- Receiving an item via dialogue
- Collecting an item via the overworld (except Q Coins)
- Finishing a race in 6th place or higher
- Receiving a license upgrade
- Completing a stamp 
    - 'Remove Double-Up Stamps' option: Since you receive an NPC reward immediately prior to receiving a stamp for roughly half the stamps in the game, a YAML option is included to merge stamps and NPC rewards into one location if they are given back-to-back in the same dialogue. Many of these 'double-up' stamps are for fairly menial tasks, so this can be a QoL setting. (This setting is currently only available in Decorations mode.)

## How to use
Download the most recent release of the APworld and add it to your custom_worlds folder. Download the most recent script zip folder and extract it.

Once the multiworld has been started and you are connected to the server via the Manual client, follow the below steps:
1. If you are starting a new run, ensure 'current_run.json' is empty (or delete it).
2. **Open PCSX2, and enable "Show Advanced Settings" under Tools. Go to System > Settings, and in the Advanced tab, enable PINE. Leave the slot as the default, 28011.**
    - If PINE is not in your advanced settings, you will likely need to update PCSX2.
3. Boot Road Trip.
4. Once you have loaded into Q's Factory, run the editor script. Once it connects to PCSX2, type the command **initAP** and press Enter.
    - **This must be done every time you boot Road Trip.**
    - If you are not running Windows, run main.py in a terminal using Python (python3 main.py)
5. Whenever you do anything listed under "Locations" above, click the corresponding location in the Manual client.
6. If the client states that you received an item, give yourself that item using the script. The name to type in the script should be exactly the same as listed in the client.
    - Example usage: **get "Progressive Tires - Set 2"** or **get "Topaz"**

## Notes on the Script
The script connects to PCSX2 using the [PINE](https://pcsx2.net/blog/2024/pcsx2-2-release/#pine-isnt-a-tree-its-a-protocol) protocol.

Command list:
- get [name of part in quotes]
- get money [amount]
- remove [name of part in quotes]
- remove money [amount]
- initAP
- help

Note that **addresses.json** *must* be in the same folder as the script in order for it to run.

**initAP** applies the below patches to the game (in the emulator's RAM only, it does not edit the ROM):
- Prevent the game from giving you any items (NPC rewards, store purchases, overworld pickups, etc.) or license upgrades
- Allow you to still buy parts that you already own in My City (the only exception to the above rule)
- Prevent gemstones and other overworld items from being removed from the overworld (these normally disappear if they are in your inventory)
- Set Tin Raceway to be a Rank A race (not required for Super A license)

Once you receive a progressive part upgrade, the script will update "**current_run.json**" to keep track of your progressive upgrades (or create it if it does not exist). Do NOT delete this file mid-run, or the script will start sending you incorrect parts!

## FAQ
- Does the Python script read/modify the ROM?
    - No - The Python script only needs to interact with PCSX2's memory (even when patching game functions)
- Why are overworld items not disappearing on collision?
    - Road Trip uses the same variable for determining whether an item should appear in the overworld as the one for whether you have the item in your inventory. The script simply patches the overworld items to always be visible.

## Known issues
- The modification to the game that stops NPCs from giving you items also prevents the game from unequipping your Flight Wing if you attempt to bring it into Ski Jump. (Have fun with that one!)