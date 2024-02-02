{
  sources ? import ./nix/sources.nix
# breaks
#,  pkgs ? import sources.nixpkgs {};
, pkgs ? import <nixpkgs> {}
, poetry2nix ? import sources.poetry2nix {}
}:

with pkgs; with lib;
let
  rswitch = poetry2nix.mkPoetryApplication rec {
    projectDir = ./.;
    python = python39;
    propagatedBuildInputs = [
      (if stdenv.hostPlatform.isDarwin
        then
      ""
        else
          firefox-unwrapped
      )
      geckodriver
    ];
    meta = {
      description = "rswitch";
      homepage = "https://github.com/Caascad/rswitch";
      license = licenses.mit;
      maintainers = [ "abryko" ];
    };
  };
in rswitch.overrideAttrs (old: rec {
  pname = "rswitch";
  version = old.version;
  name = "${pname}-${version}";
})



