{
  root,
  lockFile,
  sdk,
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  lib = pkgs.lib;
  purifier = import ((/. + "@purifier@") + "/nix/lib") { inherit lib; };
  tools = pkgs.callPackage ./tools.nix { };
  nativeFetch = pkgs.callPackage ./fetch-import.nix { inherit tools; };
  sdkVersion = import ./sdk-version.nix {
    inherit nixpkgsSrc;
    inherit (pkgs) dhall;
  };
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } {
      src = /. + root;
      lockFile = /. + lockFile;
    }
  );
  prepared = pkgs.callPackage ./environment.nix {
    inherit
      purifier
      nativeFetch
      tools
      sdkVersion
      ;
  } { inherit lock; };
in
assert lib.assertMsg (lock.data.sdk == sdkVersion) "Dhall frontend SDK changed; update the lock";
pkgs.writeText "dhall-environment-profile.json" (
  builtins.toJSON {
    output = prepared.output;
    sdk = builtins.storePath sdk;
  }
)
