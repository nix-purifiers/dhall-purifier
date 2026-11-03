{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  callPackage,
  purifier,
  nativeFetch,
  nativeInspector,
  tools,
  sdkVersion,
  gnutar,
  gzip,
}@scope:
{
  src,
  lockFile ? src + "/dhall-purifier.lock.json",
  file ? null,
  fetchers ? { },
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
  prepared = import ./environment.nix (builtins.removeAttrs scope [
    "gnutar"
    "gzip"
  ]) { inherit lock fetchers; };
  root = if file == null then builtins.head lock.data.roots else file;
  rawSource = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".dhall-purifier"
        "result"
        "__pycache__"
      ]);
  };
  source = runCommand "dhall-validated-source" { } ''
    ${python3}/bin/python3 ${../dhall_purifier}/validate-project.py ${nativeInspector}/bin/dhall-inspect ${rawSource} ${writeText "dhall-project.json" (builtins.toJSON lock.data)}
    mkdir -p "$out"
    cp -pr ${rawSource}/. "$out/"
  '';
  project =
    runCommand "dhall-native-project"
      {
        nativeBuildInputs = [
          tools.dhall
          tools.dhall-json
        ]
        ++ nativeBuildInputs;
      }
      ''
        cp -pr ${source} project
        chmod -R u+w project
        cd project
        export XDG_CACHE_HOME="$TMPDIR/private-cache"
        export XDG_DATA_HOME="$TMPDIR/private-data"
        mkdir -p "$XDG_CACHE_HOME/dhall" "$out/.cache/dhall"
        for file in ${prepared.cache}/dhall/*; do
          [ -e "$file" ] || continue
          ln -s "$file" "$XDG_CACHE_HOME/dhall/$(basename "$file")"
        done
        ${lib.getExe tools.dhall} --alpha --plain --file ${lib.escapeShellArg root} > "$out/source.dhall"
        digest=$(${lib.getExe tools.dhall} hash --file "$out/source.dhall")
        ${lib.getExe tools.dhall} encode --file "$out/source.dhall" > "$out/.cache/dhall/1220''${digest#sha256:}"
        printf 'missing %s\n' "$digest" > "$out/binary.dhall"
        ${lib.optionalString doCheck checkCommand}
      '';
  release =
    runCommand "dhall-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" package
        cp ${project}/source.dhall "$out/source.dhall"
        cp -pr ${project}/. package/
        chmod -R u+rwX package
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/dhall-package.tar.gz" -C package .
      '';
in
assert lib.assertMsg (
  lock.data.sdk == sdkVersion && lock.data.compiler == tools.dhall.version
) "Dhall compiler or frontend SDK changed; update the lock";
assert lib.assertMsg (builtins.elem root lock.data.roots) "Choose a locked Dhall root";
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
