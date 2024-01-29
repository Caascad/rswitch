{
  pkgs ? import <nixpkgs> {}
, poetry ? import( fetchTarball "https://github.com/nix-community/poetry2nix/archive/refs/tags/2024.1.1244871.tar.gz") {}
}:

with pkgs;
with pkgs.lib;
with python39Packages;
let
  rswitch = poetry.mkPoetryApplication rec {
    projectDir = ./.;
    python = pkgs.python39;
    propagatedBuildInputs = [
      (if stdenv.hostPlatform.isDarwin
        then
      ""
        else
          firefox-unwrapped
      )
      geckodriver
    ];
    meta = with pkgs.lib; {
      description = "rswitch";
      homepage = "https://github.com/Caascad/rswitch";
      license = licenses.mit;
      maintainers = with maintainers; [ "abryko" ];
    };
  };
in rswitch.overrideAttrs (old: rec {
  pname = "rswitch";
  version = old.version;
  name = "${pname}-${version}";
})



