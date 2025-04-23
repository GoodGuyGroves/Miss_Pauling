"""Utility Steam functions"""


class SteamID:
    """Performs SteamID conversions"""

    def __init__(self):
        self.steamid64ident = 76561197960265728

    def usteamid_to_commid(self, usteamid: str) -> int:
        """Converts a SteamID3 into a CommunityID"""
        for x in ["[", "]"]:
            if x in usteamid:
                usteamid = usteamid.replace(x, "")

        usteamid_split = usteamid.split(":")
        commid = int(usteamid_split[2]) + self.steamid64ident

        return commid


if __name__ == "__main__":
    steam = SteamID()
    print(steam.usteamid_to_commid("[U:1:69316398]"))
