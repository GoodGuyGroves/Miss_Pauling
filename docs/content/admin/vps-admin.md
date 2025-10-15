# VPS Administration


## SSH

To connect to the VPS that hosts the TF2 servers, use username `steam` at host `pugs.tf` and port `2222`. If you are using an ssh config file, this can get you started:

```bash
Host tf2
    HostName pugs.tf
    User steam
    Port 2222
```

## TF2 dedicated servers

At the time of writing, there are 2 servers, named `pugA` and `pugB` and they can be found in ~/servers/tf2:

```bash
steam@teamfortress:~$ ls ~/servers/tf2/
pugA  pugB
```

I have also symlinked these directories to `${HOME}` for convenience, named simply A and B:

```bash
steam@teamfortress:~$ ls -la
total 144
drwxr-x--- 14 steam steam  4096 May 20 12:38 .
drwxr-xr-x  3 root  root   4096 Apr  1 21:15 ..
lrwxrwxrwx  1 steam steam    29 May  7 20:31 A -> /home/steam/servers/tf2/pugA/
lrwxrwxrwx  1 steam steam    29 May  7 20:31 B -> /home/steam/servers/tf2/pugB/
```


### systemd

Each server is run by `systemd`, their unit files are named the same as above `pugA` and `pugB`, so you can start/stop/restart servers like so:

```bash
systemctl --user start pugA
systemctl --user stop pugB
systemctl --user restart PugA
```

Since they're run by systemd, we can then use `journalctl` to view the server logs that are being output to the srcds console, example:

```bash
journalctl --user --user-unit=pugA -f
```


### Auto-disable sv_cheats

Since __certain__ people keep leaving `sv_cheats 1` on the servers, I made a `systemd` timer for `A` and `B` so that it uses rcon to set `sv_cheats 0` twice a day, at 12:00 and again at 00:00. This might coincide with people labbing, sorry if it does, but then just set `sv_cheats` again if you're still using it.

You can check the status of the timer and it's related service with:

```bash
systemctl --user status pugA_cheats.service
systemctl --user status pugA_cheats.timer
```

You can see upcoming timers with:

```bash
systemctl --user list-timers
```


### Demo cleanup

I have also created `systemd` timers to clean up demos from both servers once a day, it deletes all demo files older than one day, so we shouldn't run out of drive space because of demo build up.

```bash
systemctl --user status pugA_demos.service
systemctl --user status pugA_demos.timer
```

### Maps

#### Map Manager

I have also created a service named `map-manager` that can be used to upload maps directly to the server, go here to upload new maps to the servers: https://fastdl.pugs.tf/. For more info on the Map Manager, [see here](./map-management/index.md).

To ensure the `systemd` service that runs this is operational:

```bash
systemctl --user status map-manager
```

#### Manual

Each server has the same set of maps so I've symlinked `pugB`'s `maps/` directory to `pugA`'s `maps/` directory:

```bash
steam@teamfortress:~$ ls -la ~/A/tf/ | grep maps
drwxrwxr-x  4 steam steam      12288 May 19 20:15 maps
steam@teamfortress:~$ ls -la ~/B/tf/ | grep maps
lrwxrwxrwx  1 steam steam         36 May  7 20:30 maps -> /home/steam/servers/tf2/pugA/tf/maps
```

So if you're uploading a new map, just drop it in `~/A/tf/maps/` and all servers will get it. Likewise, the Map Manager only uploads to this one location for all servers to get it.



### Text editor

For editing text files on the server, I have neovim (`nvim`) installed and aliased to `vi` and `vim` if you have muscle memory for those commands instead.


### rcon

I have `rcon` installed and configured with hosts in `~/.rconrc` so you can just run `rcon -s <server name> <command>` to run `rcon` commands against the servers, example:

```bash
rcon -s pugA status
```


### Sourcemod admins

The file that stores sourcemod admins is `~/A/tf/addons/sourcemod/configs/admins_simple.ini` (and the same for `B`). If you make an edit to this file on `A`, make sure to copy it over to `B` too, and vice versa. This file can't be symlinked because then sourcemod shits itself. Here is the command to copy it to where it needs to go for `B`:

```bash
cp A/tf/addons/sourcemod/configs/admins_simple.ini B/tf/addons/sourcemod/configs/admins_simple.ini
```

I can write a helper script to update the admins file if you want.

Once admins have been updated then we need to do an `sm_reloadadmins` against each server:

```bash
rcon -s pugA sm_reloadadmins
rcon -s pugB sm_reloadadmins
```


### Server configs

We now have the server configs [hosted on Github](https://github.com/GoodGuyGroves/tf2-passtime-config), you can make Pull Requests there to suggest changes. For more information on how we manage server configs, [see here](./server-configs.md).


### Misc.

I have some random crap here that may not interest you, please don't touch it because I'm probably still busy with it, example:

```bash
steam@teamfortress:~$ ls ~/
A  B  demos  demo_uploader.sh  servers  Steam  tf2_setup
```

`demo_uploader.sh` I've used before to make sure all demos have been uploaded when I thought there was an issue with the demostf plugin. `tf2_setup` is a collection of setup scripts I can use to install new servers from scratch and install plugins.
