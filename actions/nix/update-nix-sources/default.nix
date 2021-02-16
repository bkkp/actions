{ pkgs }:
pkgs.python3.pkgs.buildPythonApplication {
  name = "update-nix-sources";

  format="other";
  dontUnpack = true;

  propagatedBuildInputs = with pkgs; [
    niv
    git
    (python3.withPackages (ps: with ps; [
      typer
      requests
    ]))
  ];

  installPhase = ''
    mkdir -p $out/bin
    cp ${./update-nix-sources.py} $out/bin/update-nix-sources
    chmod +x $out/bin/update-nix-sources
  '';
}