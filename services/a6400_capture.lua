#!/usr/bin/env lua
--
-- a6400 tethered capture — single persistent gphoto2 session.
--
-- This script is the long-lived service process. It runs
-- gphoto2 --capture-tethered in a loop: gphoto2 occasionally exits (a known
-- quirk after its initial probe, or when the camera link blips), and we simply
-- relaunch it after letting the kernel fully release the USB device. Because
-- the SCRIPT stays alive, systemd sees a healthy unit and never fast-restarts
-- into a device-claim collision.
--
-- There is only ever ONE gphoto2 at a time: we hold a single session and only
-- start a new one after the previous has exited and the device has settled.

local DOWNLOAD_DIR = "/home/dietpi/downloads"

local function emit(msg)
    print(msg)
    io.flush()
end

local function sleep(sec)
    os.execute("sleep " .. sec)
end

os.execute("mkdir -p '" .. DOWNLOAD_DIR .. "'")

local function next_filenumber()
    local highest = 0
    local p = io.popen("ls -1 '" .. DOWNLOAD_DIR .. "' 2>/dev/null")
    if p then
        for name in p:lines() do
            local n = tonumber(name:match("^(%d+)%.%a+$"))
            if n > highest then highest = n end
        end
        p:close()
    end
    return highest + 1
end

local function kill_competitors()
    os.execute("pkill -f gvfs-gphoto2 2>/dev/null")
    os.execute("pkill -x gphoto2 2>/dev/null")
end

local function build_capture_command(startnum)
    return "cd '" .. DOWNLOAD_DIR .. "' && gphoto2 --capture-tethered --force-overwrite --filenumber="
        .. startnum .. " --filename '" .. DOWNLOAD_DIR .. "/%05n.%C'"
end

kill_competitors()
sleep(2)

emit("[+] a6400 tethered monitor started.")

while true do
    local startnum = next_filenumber()
    emit(string.format("[*] Tethered session starting (next file: %05d).", startnum))

    os.execute(build_capture_command(startnum))

    emit("[*] gphoto2 exited; releasing USB device, reconnecting in 5s...")
    kill_competitors()
    sleep(5)
end
