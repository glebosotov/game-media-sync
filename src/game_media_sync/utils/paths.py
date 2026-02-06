from ..platforms.steam.utils import GetAccountId

with open("autoscreenshot.path", "w") as f:
    f.writelines(
        """
[Path]
PathModified=%h/.local/share/Steam/userdata/{0}/760/screenshots.vdf
Unit=autoscreenshot.service
    """.format(GetAccountId())
    )

print("Successfully generated autoscreenshot.path (probably)")
