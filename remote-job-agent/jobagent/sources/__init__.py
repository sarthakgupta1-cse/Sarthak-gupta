from .base import Source
from .boards import (HimalayasSource, JobicySource, RemoteOKSource, RemotiveSource,
                     WeWorkRemotelySource, WorkingNomadsSource)
from .ats import AshbySource, GreenhouseSource, LeverSource
from .manual import ManualSource

__all__ = ["Source", "HimalayasSource", "JobicySource", "RemoteOKSource", "RemotiveSource",
           "WeWorkRemotelySource", "WorkingNomadsSource", "AshbySource", "GreenhouseSource",
           "LeverSource", "ManualSource", "build_sources"]


def build_sources(settings: dict, http, companies: dict) -> list[Source]:
    sc = settings["sources"]
    out: list[Source] = []
    if sc["himalayas"]["enabled"]:
        out.append(HimalayasSource(http, sc["himalayas"]))
    if sc["remotive"]["enabled"]:
        out.append(RemotiveSource(http, sc["remotive"]))
    if sc["remoteok"]["enabled"]:
        out.append(RemoteOKSource(http, sc["remoteok"]))
    if sc["jobicy"]["enabled"]:
        out.append(JobicySource(http, sc["jobicy"]))
    if sc["weworkremotely"]["enabled"]:
        out.append(WeWorkRemotelySource(http, sc["weworkremotely"]))
    if sc["workingnomads"]["enabled"]:
        out.append(WorkingNomadsSource(http, sc["workingnomads"]))
    if sc["ats_boards"]["enabled"]:
        out.append(GreenhouseSource(http, companies.get("greenhouse", [])))
        out.append(LeverSource(http, companies.get("lever", [])))
        out.append(AshbySource(http, companies.get("ashby", [])))
    if sc["manual"]["enabled"]:
        out.append(ManualSource(sc["manual"]))
    return out
