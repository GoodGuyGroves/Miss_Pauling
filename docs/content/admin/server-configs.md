# Server Configs

The server configs are managed in a gitops way, with the source of truth being [this repository](https://github.com/GoodGuyGroves/tf2-passtime-config)

If you'd like to see a change to the server config, send a Pull Request through with your change so we can review and merge it.

If you're an admin who is regularly involved and you make frequent changes, send me your Github username so I can add you directly to the repository as a contributor so you can yolo push changed directly to `main`.


## Deploy workflow

There is a deployment workflow that can be [found here](https://github.com/GoodGuyGroves/tf2-passtime-config/blob/main/.github/workflows/deploy-tf2-configs.yml).

It triggers on commits to `main` and makes changes to servers based on the servers defined in the [config.json](https://github.com/GoodGuyGroves/tf2-passtime-config/blob/main/config.json) file in the repository.

When this deploy workflow triggers, it does the following:

1. Sets up SSH so it can connect to the VPS hosting the TF2 servers
1. Changes into the `~/servers/tf2/tf2-passtime-config` directory on the server which is a clone of the git repo
1. Pulls the latest changes and then runs the [`deploy.sh`](https://github.com/GoodGuyGroves/tf2-passtime-config/blob/main/deploy.sh) script, which does the following:
    1. Pulls values set in the git repo `secrets` and `variables` and makes them available to the VPS
    1. Stores the old rcon password (in case it is about to change)
    1. Copies all config files from the git repo over the config files currently on the TF2 server
    1. Updates server.cfg with values pulled from the git repo (hostname, rcon password, etc)
    1. Updates the `~/.rconrc` file used for the `rcon` tool used from the VPS
    1. Sends a notification to the server that there is new config and that a map change is required
1. Does a quick cleanup


## Validating a change

If you have had a PR merged or if you've pushed straight to `main` and you'd like to validate your change, first check [the Github Actions tab](https://github.com/GoodGuyGroves/tf2-passtime-config/actions) to see if your deploy ran.

If you click into your deploy, you should see a step called "Deploy to server" which is the most likely point of failure. If any of these steps have failed then you'll need to probably rope me (Russ) in, or anyone else who has admin perms on the server/on Github.

If your deploy has run successfully, your changes should be on the server, so now a map change is required for the new config to be picked up.
