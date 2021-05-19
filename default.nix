{
pkgs ? import <nixpkgs> {} 
}: 

with pkgs;
with pkgs.lib;
with python3Packages;
buildPythonApplication rec {
    pname = "rswitch";
    version = "1.0.0";
    unpackPhase = ":";
    phases= ["installPhase" "fixupPhase"];
    propagatedBuildInputs = [
      (if stdenv.hostPlatform.isDarwin
        then
	  ""
        else
          firefox-unwrapped
      )
      geckodriver
      (python3.withPackages (pythonPackages: with pythonPackages; [ 
        requests
        selenium
        click
      ]))
    ]; 
    src=".";
    buildInputs = [
      makeWrapper
    ];
    installPhase = ''
      mkdir -p $out/bin 
      install -m755 -D ${./rswitch.py} $out/bin/rswitch
      substituteInPlace $out/bin/rswitch --replace RSWITCH_VERSION ${version}
    '';
    meta = with pkgs.lib; { 
    description = "rswitch"; 
    homepage = "https://github.com/Caascad/rswitch"; 
    license = licenses.mit; 
    maintainers = with maintainers; [ "karim-oueslati" ]; 
  }; 

  }
