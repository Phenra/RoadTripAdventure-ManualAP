from pine.pine import Pine
from time import sleep
import shlex
import json
import os

BITS_IN_BYTE = 8
MIPS_INSTRUCTION_SIZE = 4
CMD_GET = "get"
CMD_REMOVE = "remove"
CMD_INIT = "initAP"
CMD_HELP = "help"
NOP_BYTES = bytes([0,0,0,0])
LIFE_BODY_BIT_OFFSET = 149

def setBit(bytes : bytes, bitIndex : int, endianness="little") -> bytes:
    val = bytes_to_int(bytes, endianness)

    if(len(bytes) * BITS_IN_BYTE > bitIndex):
        val = val | (1 << bitIndex)
        val = int_to_bytes(val, len(bytes), endianness)
    else:
        raise ValueError("Error in setBit: Bit index out of range")
    
    return val

def clearBit(bytes : bytes, bitIndex : int, endianness="little") -> bytes:
    val = bytes_to_int(bytes, endianness)

    if(len(bytes) * BITS_IN_BYTE > bitIndex):
        val = val & ~(1 << bitIndex)
        val = int_to_bytes(val, len(bytes), endianness)
    else:
        raise ValueError("Error in clearBit: Bit index out of range")
    
    return val

def isBitSet(bytes : bytes, bit : int) -> bool:
    # If clearBit does not change the value, that means the bit is not set
    return bytes != clearBit(bytes, bit)

def updateBit(cmd : str, bytes : bytes, bit: int, endianness="little") -> bytes:
    if(cmd == CMD_GET):
        return setBit(bytes, bit, endianness)
    elif(cmd == CMD_REMOVE):
        return clearBit(bytes, bit, endianness)
    else:
        raise ValueError("Error: First argument is not valid, but we're already handling a collectible upgrade... how did you get here??")

# https://stackoverflow.com/a/30375198
# Changed function to require a length value - Python removes leading 0s from bytes, which was causing problems.
def int_to_bytes(x: int, len : int, endianness="little") -> bytes:
    return x.to_bytes(len, endianness)

def bytes_to_int(xbytes: bytes, endianness="little") -> int:
    return int.from_bytes(xbytes, endianness)

def bytes_length(x : int) -> int:
    return (x.bit_length() + 7) // 8

def init(data : dict, pine : Pine):
    # Inject an ASM function that prevents purchased items from being added to your inventory, *except* in My City.
    #     My City's part shop does not contain any locations, and is used exclusively for repurchasing parts you've
    #     already obtained.

    # At 0x2697d8, change the ASM instruction (which is currently a jump-and-link to the function that handles updating  
    #     your inventory) to a jal to 0x2EA0A8. This is a region of memory containing unused non-English strings.
    #     We'll use this memory as a code cave for a new hook.
    pine.write_bytes(0x2697D8, bytes([0x2A, 0xA8, 0x0B, 0x0C])) # jal 0x002EA0A8 (0C0BA82A)
    
    # In our hook, test if the current region index is 9 (My City).
    #     If it's not, simply return.
    #     If it is, jump (not jal) to the function that updates your inventory.
    pine.write_bytes(0x2EA0A8, bytes([0x33, 0x00, 0x08, 0x3C])) # lui t0, 0x0033 (3C080033)
    pine.write_bytes(0x2EA0AC, bytes([0x23, 0x59, 0x08, 0x25])) # addiu t0, t0, 0x5923 (25085923)
    pine.write_bytes(0x2EA0B0, bytes([0x00, 0x00, 0x08, 0x81])) # lb t0, 0x0(t0) (81080000)
    pine.write_bytes(0x2EA0B4, bytes([0x09, 0x00, 0x09, 0x24])) # addiu t1, zero, 0x9 (24090009)
    pine.write_bytes(0x2EA0B8, bytes([0x03, 0x00, 0x09, 0x15])) # bne t0, t1, 0x2EA0C8 (15090003)
    pine.write_bytes(0x2EA0BC, NOP_BYTES) # nop (00000000)
    pine.write_bytes(0x2EA0C0, bytes([0xB0, 0xF4, 0x08, 0x08])) # j 0x23D2C0 (0808F4B0)
    pine.write_bytes(0x2EA0C4, NOP_BYTES) # nop (00000000)
    pine.write_bytes(0x2EA0C8, bytes([0x08, 0x00, 0xE0, 0x03])) # jr ra (03E00008)
    pine.write_bytes(0x2EA0CC, NOP_BYTES) # nop (00000000)

    # Remove the default parts from the My City part shop
    # The My City part shop has several parts that are always sold there, even if you've never received them.
    #     Since My City's part shop is used exclusively for repurchasing parts you already own in AP, 
    #     these are not locations in the multiworld.
    pine.write_bytes(0x2DC76C, bytes([0])) # HG Racing Tires
    pine.write_bytes(0x2DC771, bytes([0])) # Speed MAX Engine
    pine.write_bytes(0x2DC778, bytes([0])) # Wide Transmission
    pine.write_bytes(0x2DC785, bytes([0])) # Spoke 7
    pine.write_bytes(0x2DC79D, bytes([0])) # Horse Horn, Train Horn

    # Change the license requirement for entering Tin Raceway to the A License
    #     This does not make Tin Raceway a required race for obtaining the Super A License
    pine.write_bytes(0x2BDF63, bytes([2]))

    # Also for Tin Raceway, modify the assembly instruction at the below location to be an unconditional branch.
    #     This branch typically checks whether the race you're trying to enter is Tin Raceway. 
    #     If it is, it then checks if you've completed stamp 100 (Became the President), and prevents you from
    #     entering if you haven't (displays "Under construction").
    pine.write_bytes(0x239E12, bytes([0,0x10]))

    # Write NOP in dialogue handler function to prevent items from being given as rewards
    pine.write_bytes(0x23A0B4, NOP_BYTES)

    # Write NOP in dialogue handler function to prevent items from being equipped to you
    #   (e.g. Billboards, Wing Set + Propeller)
    pine.write_bytes(0x23B984, NOP_BYTES)

    # NOP the line of assembly that gives the player license upgrades
    pine.write_bytes(0x236704, NOP_BYTES)

    # Write NOPs to prevent overworld items from adding to your inventory on collision
    overworldItemJALs = [
        # First location = NOP function call for playing pickup sound
        #     If we do not NOP this, it will play the sound on every frame, which (although pretty funny) 
        #     is loud and sounds bad
        # Second location = NOP function call for inventory update
        0x2409E0,           # Peach  # 0x2409D0 for sound,  not needed for the Peach
        0x25C02C, 0x25C03C, # Wallet 
        0x25C2A4, 0x25C2B4, # Fluffy Mushroom
        0x25C3E0, 0x25C3F0, # Amethyst
        0x25C4C4, 0x25C4D4, # Moonstone
        0x25C5F8, 0x25C608, # Small Bottle
        0x25C6D8, 0x25C6E8, # Black Opal
        0x25C7B8, 0x25C7C8, # Papu Flower
        0x25C8F4, 0x25C904, # Ruby
        0x25CAD8, 0x25CAE8, # Fountain Pen
        0x25CBB8, 0x25CBC8, # Blue Sapphire
        0x25D498, 0x25D4A8, # Topaz
        0x25D5A8, 0x25D5B8  # Emerald
    ]
    for address in overworldItemJALs:
        pine.write_bytes(address, NOP_BYTES)
    
    # Also modify these functions to prevent overworld items from disappearing when we add that item to our
    #    inventory. (Road Trip uses the status of the item in your inventory to determine whether it should
    #    appear in the overworld.)
    overworldItemInventoryChecks = [
        0x25BF9C, # Wallet 
        0x25C218, # Fluffy Mushroom
        0x25C350, # Amethyst
        0x25C434, # Moonstone
        0x25C568, # Small Bottle
        0x25C648, # Black Opal
        0x25C728, # Papu Flower
        0x25C868, # Ruby
        0x25CA48, # Fountain Pen
        0x25CB28, # Blue Sapphire
        0x25D410, # Topaz
        0x25D520  # Emerald
    ]

    for address in overworldItemInventoryChecks:
        pine.write_bytes(address, bytes([0x00, 0x00, 0x02, 0x24])) # addiu v0,zero,0x0 (24020000)
        pine.write_bytes(address+4, NOP_BYTES) # Remove branch delay slots

    print("initAP Successful")

def getPartData(table : dict, item : str) -> tuple[bool, list]:
    itemFound = False
    itemData = [None, None, None]
    for partType in table:
        # Check that we're reading from a nested dictionary (if not, short-curcuit), then check if item is in bitOffsets
        if isinstance(table[partType], dict) and item in table[partType]["bitOffsets"]:
            print("Bit:", table[partType]["bitOffsets"][item])

            inventoryAddress = int(table[partType]["inventoryAddress"], 16) # Addresses in data object are hex strings e.g. "0x2DC56C", need to convert to int
            bit = table[partType]["bitOffsets"][item]
            shopAddress = int(table[partType]["shopAddress"], 16)

            itemData = [inventoryAddress, bit, shopAddress]
            itemFound = True
            break
    
    return itemFound, itemData

def updatePart(table : dict, pine : Pine, cmd : str, item : str):
    MAX_QUANTITY = table["maxQuantity"]
    SIZE_IN_BYTES = table["sizeInBytes"]

    partData = getPartData(table, item)
    itemFound = partData[0]
    inventoryAddress, bit, shopAddress = partData[1]

    if itemFound:
        # Check each quantity bitfield. (Road Trip uses separate bitfields for your 1st/2nd/etc. copies of a 
        #     part - i.e. bitfield 1 tracks your first copy of all parts, bitfield 2 tracks all second
        #     copies, etc.) Once we find one that is empty, either add the part to that bitfield, or remove 
        #     it from the previous one, depending on the command.
        i = 0
        prevBytes = None
        while i < MAX_QUANTITY:
            bytes = pine.read_bytes(inventoryAddress, SIZE_IN_BYTES)

            # Update Inventory
            if not isBitSet(bytes, bit):
                print("Open bit found")
                # If we're gaining a part, set this bit to 1 in the current set of bytes
                #    (i.e. current quantity and address)
                if(cmd == CMD_GET):
                    bytes = setBit(bytes, bit)
                # If we're losing a part, set this bit to 0 in the *previous* set of bytes 
                #   (i.e. previous quantity and address)
                elif(cmd == CMD_REMOVE):
                    if(i > 0):
                        bytes = prevBytes
                        inventoryAddress -= SIZE_IN_BYTES
                        bytes = clearBit(bytes, bit)
                break
            else:
                inventoryAddress += SIZE_IN_BYTES
                prevBytes = bytes
                i = i + 1

        if (i == MAX_QUANTITY):
            # If we run the full while loop without finding an unset bit, address gets incremented out of range
            inventoryAddress -= SIZE_IN_BYTES 
            # If we checked every bit, and all were already set, then we currently have the maximum number of an item.
            #   If the command was remove, we need to remove the part from the last quantity bitfield.
            if(cmd == CMD_REMOVE):
                bytes = clearBit(bytes, bit)

        # Finally, write the updated inventory bitfield into memory.
        print("Writing to address", hex(inventoryAddress))
        pine.write_bytes(inventoryAddress, bytes)

        #updateItemInCurrentRun(cmd, item)
    else:
        print("Error: Item not found")

def updateProgressiveUpgrade(data : dict, pine : Pine, cmd : str, item : str):
    # Determine which table this part is in, and which part in the progression to give to/remove from the player
    itemType = item.split(" ")[1]
    typeObj = None
    match itemType:
        case "License":
            typeObj = data["licenses"]
        case "Tires":
            typeObj = data["parts"]["tires"]
        case "Engine":
            typeObj = data["parts"]["engines"]
        case "Chassis":
            typeObj = data["parts"]["chassis"]
        case "Transmission":
            typeObj = data["parts"]["transmission"]
        case "Steering":
            typeObj = data["parts"]["steering"]
        case "Brakes":
            typeObj = data["parts"]["brakes"]
        case _:
            print("Error: Invalid progressive item type provided")
            return
    
    ensureCurrentRunFileExists()
    
    with open("current_run.json", "r") as file:
        currentRun = json.load(file)
    
    if item in currentRun:
        itemIndex = currentRun[item]
    else:
        itemIndex = 0

    if cmd == CMD_GET:
        itemIndex += 1

    if cmd == CMD_REMOVE and itemIndex <= 0:
        print("Error: Cannot remove progressive upgrade since we do not currently have any of this type.")
        return

    # Search through the items of this part type to see if we can find one with a bit offset that matches
    #     our new itemIndex.
    newItem = None
    if itemType != "Tires" and itemType != "License":
        for name, value in typeObj["bitOffsets"].items():
            if value == itemIndex:
                newItem = name
                break
    # Tires are not provided in their internal order, use the below order instead
    elif itemType == "Tires":
        progressiveTireOrder = [
            "Normal Tires",
            "Off-Road Tires", 
            "Sports Tires", 
            "Studless Tires", 
            "Semi-Racing Tires", 
            "Wet Tires", 
            "HG Off-Road Tires", 
            "HG Studless Tires", 
            "HG Wet Tires", 
            "Racing Tires", 
            "Big Tires", 
            "HG Racing Tires"
            "Devil Tires"
        ]
        newItem = progressiveTireOrder[itemIndex]
    # Licenses do not use bit offsets, they use specific values instead
    else:
        for name, value in typeObj["values"].items():
            if value == itemIndex:
                newItem = name
                break
    if newItem != None:
        if itemType != "License":
            updatePart(data["parts"], pine, cmd, newItem)
        else:
            setLicense(data["licenses"], pine, cmd, newItem)
    else:
        print("Error: Progressive Upgrade function could not find a valid new item to award.")
        return

    # Update our stored Python object that represents our JSON data
    currentRun[item] = itemIndex

    if cmd == CMD_REMOVE:
        currentRun[item] -= 1

    # Write the updated object back to the current_run file
    with open("current_run.json", "w") as file:
        json.dump(currentRun, file, indent=4)

def updateCollectible(table : dict, pine : Pine, cmd : str, item : str):
    print("Bit:", table["bitOffsets"][item])

    address = int(table["address"], 16) # Addresses in data object are hex strings e.g. "0x2DC56C", need to convert to int
    bit = table["bitOffsets"][item]

    bytes = pine.read_bytes(address, table["sizeInBytes"])

    # Update Inventory
    bytes = updateBit(cmd, bytes, bit)
    
    print("Writing to address", hex(address))
    pine.write_bytes(address, bytes)

    #updateItemInCurrentRun(cmd, item)

def updateBody(table : dict, pine : Pine, cmd : str, item : str):
    if item != "Life Body":
        if not item[0:6] == "Body Q":
            print("Error: updateBody called, but item is not a body")
            return
        try:
            value = int(item[6:])
            if item != "Body Q150":
                value -= 1 # All bodies except Q150 are at an offset of their body number minus 1
        except:
            print("Error: Body value provided does not appear to be a number")
    else:
        value = LIFE_BODY_BIT_OFFSET

    if value > 150 or value < 0:
        print("Error: Invalid body value (greater than 150 or less than 0")
        return
    else: # We should now have a valid body value!
        address = int(table["address"], 16) # Addresses in data object are hex strings e.g. "0x2DC56C", need to convert to int
        bytes = pine.read_bytes(address, table["sizeInBytes"])
        bytes = updateBit(cmd, bytes, value)
        print("Writing to address", hex(address))
        pine.write_bytes(address, bytes)

        #updateItemInCurrentRun(cmd, item)

def setLicense(table : dict, pine : Pine, cmd : str, item : str):
    address = int(table["address"], 16) # Addresses in data object are hex strings e.g. "0x2DC56C", need to convert to int
    value = table["values"][item]
    size = table["sizeInBytes"]

    if cmd == CMD_REMOVE:
        if value > 0:
            value -= 1
        else:
            print("Error: Cannot remove C License")
            return

    print("Writing to address", hex(address))
    pine.write_bytes(address, int_to_bytes(value, size))

    #updateItemInCurrentRun(cmd, item)

def updateMoney(table : dict, pine : Pine, cmd : str, value : str):
    if value == None or not value.isdigit:
        print("Error: Money amount provided is not an integer.")
        return
    else:
        value = int(value)

    if cmd == CMD_REMOVE:
        value *= -1

    address = int(table["address"], 16) # Addresses in data object are hex strings e.g. "0x2DC56C", need to convert to int

    bytes = pine.read_bytes(address, 4)
    currentMoney = bytes_to_int(bytes)

    if value > 0:
        if currentMoney + value > 999999: # Prevent exceeding maximum money amount
            value = 999999 - currentMoney
            print(f"Adding {value} to money (cannot exceed 999,999)")
        else:
            print(f"Adding {value} to money")
    elif value < 0:
        if currentMoney + value < 0: # Prevent reducing money below 0
            value = -1 * currentMoney
            print(f"Subtracting {-1 * value} from money (cannot go below 0)")
        else:
            print(f"Subtracting {-1 * value} from money")
    else:
        print("Value is 0, no change")
        return

    bytes = int_to_bytes(currentMoney + value, 4)
    pine.write_bytes(address, bytes)

def initializeCurrentRun():
    with open("current_run.json", "w") as file:
        json.dump({}, file)

def ensureCurrentRunFileExists():
    if not os.path.exists("current_run.json"):
        initializeCurrentRun()
    else:
        with open("current_run.json", "r") as file:
            # A blank JSON file will cause exceptions later. Let's initialize it to an empty JSON object.
            size = os.path.getsize("current_run.json")
            if size == 0:
                initializeCurrentRun()

def updateItemInCurrentRun(cmd : str, itemStr : str):
    if cmd == CMD_GET:
        writeItemToCurrentRun(itemStr)
    elif cmd == CMD_REMOVE:
        removeItemFromCurrentRun(itemStr)
    else:
        print("Error: writeItemToCurrentRun called, but command is neither get nor remove?")

def writeItemToCurrentRun(itemStr: str):
    ensureCurrentRunFileExists()
    with open("current_run.json", "r") as file:
        currentRun = json.load(file)
        currentRun[itemStr] = 1
    with open("current_run.json", "w") as file:
        json.dump(currentRun, file, indent=4)

def removeItemFromCurrentRun(itemStr : str):
    ensureCurrentRunFileExists()
    with open("current_run.json", "r") as file:
        currentRun = json.load(file)
        for name, value in currentRun.items():
            if name == itemStr:
                currentRun.pop(itemStr)
                break
    with open("current_run.json", "w") as file:
        json.dump(currentRun, file, indent=4)

def main():
    with open("addresses.json", "r") as file:
        data = json.load(file)

    print("--------------------------------------")
    print("Road Trip Adventure Inventory Editor")
    print("--------------------------------------")
    loadingMsg = "Attempting to connect to PCSX2 via PINE.\n" \
    "To enable PINE, go to Tools and click 'Show Advanced Settings', then go to System > Settings " \
    "and click the now-visible 'Advanced' tab.\nScroll to the PINE section at the bottom and click 'Enable'.\n" \
    "The port can be left at the default setting.\n"
    print(loadingMsg)

    pine = Pine()

    # Wait for a connection to PCSX2...
    print("Attempting to connect...")
    while pine.is_connected() == False:
        pine.connect()
        sleep(1)
    print("Connected to PCSX2 via PINE!\n")

    # Wait for the current game to be Road Trip...
    gameLoaded = False
    print("Waiting for Road Trip to start...")
    while not gameLoaded:
        try:
            gameId = pine.get_game_id()
            if gameId == "SLUS-20398": 
                gameLoaded = True
        except:
            # There doesn't appear to be a function in the included pine.py script that can test
            #    specifically for whether PCSX2 is running but does NOT currently have a game loaded.
            #    'get_game_id()' actually raises an exception if a game is not loaded.
            #
            # While I don't like it, this seems to mean that our best option is to just wrap the
            #    call in a try/except block, and if it throws, capture that, ignore the exception,
            #    and try again after the sleep delay.
            pass
        finally:
            sleep(1)
    print("Road Trip loaded!\n")

    # Process user commands
    while(True):
        argv = input("Enter a command ('help' for options): ")
        try:
            argv = shlex.split(argv)
            commandParsed = True
        except:
            print("Error: Could not parse command.\n")
            commandParsed = False

        if commandParsed:
            # Read arguments
            cmd = None
            item = None
            value = None
            if(len(argv) >= 1):
                cmd = argv[0]
            if(len(argv) >= 2):
                item = argv[1]
            if(len(argv) >= 3):
                value = argv[2] # Currently only used for money

            # Process arguments
            if(cmd == CMD_INIT):
                init(data, pine)
            elif(cmd == CMD_HELP):
                print()
                print("Command list")
                print("---------------------------------------------------------------")
                print("get [name of part in quotes]       Add a part to your inventory")
                print("get money [amount]                 Add amount to your current money")
                print("remove [name of part in quotes]    Remove a part from your inventory")
                print("remove money [amount]              Subtract amount from your current money")
                print("initAP                             If playing RTA AP manual, run after loading Q's Factory (but NOT before!)")
                print()
                print("initAP patches several functions that would interfere with the manual Archipelago randomizer:")
                print("- Prevents shop purchases from going to your inventory (except in the My City part shop)")
                print("- Prevents NPC rewards from being added to your inventory")
                print("- Prevents receiving license upgrades from completing all races within a rank")
                print("- Prevents NPCs from equipping parts to you (e.g. in the Temple Under the Sea)")
                print("- Makes overworld items always visible, even if the player already has that item (e.g gemstones)")
                print("- Allows access to Tin Raceway with just the Rank A license (allows Tin Raceway to be a location check)")
                print()
            elif(cmd == CMD_GET or cmd == CMD_REMOVE):               
                if item:
                    # Remove the " (Key)" string if included
                    item = item.replace(" (Key)", "")
                    
                    # If the item is a progressive upgrade...
                    if (item in data["progressiveUpgrades"]["names"]):
                        updateProgressiveUpgrade(data, pine, cmd, item)

                    # Else, if it is a collectible...
                    elif (item in data["collectibles"]["bitOffsets"]):
                        updateCollectible(data["collectibles"], pine, cmd, item)

                    # Else, if it is a body...
                    elif (item[0:6] == "Body Q" or item == "Life Body"):
                        updateBody(data["bodies"], pine, cmd, item)

                    # Else, if it is a license...
                    elif (item in data["licenses"]["values"]):
                        setLicense(data["licenses"], pine, cmd, item)
                    
                    # Else, if it is money...
                    elif (item.lower() == "money"):
                        updateMoney(data["money"], pine, cmd, value)

                    # Else, we check each table in Parts - and if in none, do nothing
                    else:
                        updatePart(data["parts"], pine, cmd, item)
                else:
                    print("Error: No item supplied!")
            else:
                print("Error: First argument is not valid!")
            
            print()

if __name__ == "__main__":
    main()
