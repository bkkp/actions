{ pkgs }:

let
  curl = pkgs.curl;

in pkgs.writeShellScriptBin "deploy-to-bkknix"
  ''
  # Script argumens: svadil_token, source_to_update

  ${curl}/bin/curl \
    -X POST \
    -H "Accept: application/vnd.github.v3+json" \
    -u svadil:$1 \
    https://api.github.com/repos/bkkp/bkknix/actions/workflows/6826393/dispatches \
    -d "{\"ref\": \"fix-update-source\", \"inputs\": { \"source\": \"$2\" }}"
  ''
