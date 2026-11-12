{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  dhall,
  dhall-json,
  dhall-lsp-server,
  nativeInspector,
  tools,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
  cacert,
  writeText,
}:
let
  originals = writeText "dhall-original-programs.json" (
    builtins.toJSON {
      dhall = lib.getExe dhall;
      dhall-to-json = lib.getExe' dhall-json "dhall-to-json";
      json-to-dhall = lib.getExe' dhall-json "json-to-dhall";
      dhall-lsp-server = lib.getExe dhall-lsp-server;
    }
  );
in
stdenvNoCC.mkDerivation {
  pname = "dhall-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/dhall-purifier"
    cp -r dhall_purifier pkgs lib-overlays native "$out/lib/dhall-purifier/"
    mkdir -p "$out/lib/dhall-purifier/locked-tools"
    ln -s ${tools.dhall} "$out/lib/dhall-purifier/locked-tools/dhall"
    ln -s ${tools.dhall-json} "$out/lib/dhall-purifier/locked-tools/json"
    ln -s ${tools.dhall-lsp-server} "$out/lib/dhall-purifier/locked-tools/lsp"
    install -m755 bin/dhall-purifier "$out/bin/dhall-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/dhall-purifier/pkgs/build-dhall-project/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/dhall-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default DHALL_PURIFIER_GH ${gh}/bin/gh \
      --set DHALL_PURIFIER_ORIGINAL_DHALL ${lib.getExe dhall} \
      --set DHALL_PURIFIER_PROGRAMS ${originals} \
      --set DHALL_PURIFIER_INSPECTOR ${nativeInspector}/bin/dhall-inspect \
      --set DHALL_PURIFIER_COMPILER_VERSION ${dhall.version} \
      --set DHALL_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set DHALL_PURIFIER_SDK "$out"
    for program in dhall dhall-to-json json-to-dhall dhall-lsp-server; do
      makeWrapper "$out/bin/dhall-purifier" "$out/bin/$program" --add-flags "--native=$program"
    done
  '';
  meta = {
    description = "Native Dhall with locked Nix-resolved imports";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "dhall-purifier";
  };
}
