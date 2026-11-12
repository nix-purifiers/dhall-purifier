{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  nativeFetch,
  tools,
  sdkVersion,
  ...
}@scope:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  nativeURLFetch =
    args:
    let
      matches = builtins.filter (e: e.hash == args.hash && builtins.elem e.url args.urls) checked.entries;
    in
    assert lib.assertMsg (builtins.length matches == 1) "Dhall import fetch is ambiguous";
    nativeFetch (builtins.head matches);
  tree = purifier.tree (
    {
      name = "dhall-native-imports";
      entries = checked.entries;
      fetchurl = nativeURLFetch;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  packages = builtins.listToAttrs (
    map (entry: {
      name = entry.dhall.hash;
      value = runCommand "dhall-native-package" { } ''
        mkdir -p "$out/.cache/dhall"
        cp ${tree}/${entry.path} "$out/.cache/dhall/1220${entry.dhall.hash}"
        ${lib.getExe tools.dhall} decode --file ${tree}/${entry.path} > "$out/source.dhall"
        actual=$(${lib.getExe tools.dhall} hash --file "$out/source.dhall")
        test "$actual" = 'sha256:${entry.dhall.hash}'
        printf '%s\n' 'missing sha256:${entry.dhall.hash}' > "$out/binary.dhall"
      '';
    }) checked.entries
  );
  cache = runCommand "dhall-locked-cache" { } ''
    mkdir -p "$out/dhall"
    ${lib.concatMapStrings (entry: ''
      ln -s ${packages.${entry.dhall.hash}}/.cache/dhall/1220${entry.dhall.hash} "$out/dhall/1220${entry.dhall.hash}"
    '') checked.entries}
  '';
  manifest = writeText "dhall-environment.json" (
    builtins.toJSON {
      inherit cache packages;
      sdk = sdkVersion;
      version = tools.dhall.version;
      programs = {
        dhall = lib.getExe tools.dhall;
        dhall-to-json = lib.getExe' tools.dhall-json "dhall-to-json";
        json-to-dhall = lib.getExe' tools.dhall-json "json-to-dhall";
        dhall-lsp-server = lib.getExe tools.dhall-lsp-server;
      };
    }
  );
  output = runCommand "dhall-locked-environment" { } ''
    mkdir -p "$out"
    ln -s ${manifest} "$out/manifest.json"
  '';
in
{
  inherit
    output
    tree
    cache
    packages
    ;
}
