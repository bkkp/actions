{ pkgs }:

let
  python-env = pkgs.python38.withPackages(ps: with ps; [
    typer
    requests
  ]);

in pkgs.python3.pkgs.buildPythonApplication {
  name = "update-nix-sources";
  version = "21.03.1001";
  src = ./.;

  propagatedBuildInputs = with pkgs; [
    python-env
    nix
    niv
    git
  ];
}