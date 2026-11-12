final: prev: {
  dhall-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
