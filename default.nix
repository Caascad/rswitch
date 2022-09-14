{
pkgs ? import <nixpkgs> {} 
}: 

with pkgs;
with pkgs.lib;
with python39Packages;
let 
  rswitch = poetry2nix.mkPoetryApplication rec {
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



