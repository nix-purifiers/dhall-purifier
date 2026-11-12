{ lib }:
{
  src,
  lockFile ? src + "/dhall-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  digest = s: builtins.isString s && builtins.match "[a-f0-9]{64}" s != null;
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "dhall"
    && builtins.isString (data.sdk or null)
    && builtins.isString (data.compiler or null)
    && builtins.isList (data.roots or null)
    && data.roots != [ ]
    && builtins.all relative data.roots
    && builtins.isAttrs (data.project or null)
    && builtins.all (
      name:
      relative name && builtins.pathExists (src + "/${name}") && builtins.isList data.project.${name}
    ) (builtins.attrNames data.project)
    && builtins.all (name: data.project ? ${name}) data.roots
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && (e.mirrors or null) == [ ]
      && builtins.isString (e.url or null)
      && builtins.match "https?://.*" e.url != null
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isAttrs (e.dhall or null)
      && digest (e.dhall.hash or null)
      && (e.path or null) == "cache/1220${e.dhall.hash}"
      && builtins.elem (e.dhall.mode or null) [
        "Code"
        "RawText"
        "RawBytes"
      ]
      && builtins.isString (e.dhall.expression or null)
    ) entries
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs (data.inputs or null);
  valid =
    shape
    && builtins.length entries == builtins.length (lib.unique (map (e: e.path) entries))
    && builtins.attrNames data.inputs == builtins.sort builtins.lessThan (lib.unique data.extraInputs)
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.isAttrs data.inputs.${name}
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs);
in
{
  purifier = "dhall";
  inherit data entries;
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
  problems = lib.optional (!valid) "Invalid or stale Dhall lock; update the lock";
}
