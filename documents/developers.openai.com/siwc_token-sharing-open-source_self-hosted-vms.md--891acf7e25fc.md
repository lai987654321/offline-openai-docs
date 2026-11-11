# Self-hosted VMs

> For the complete documentation index, see [llms.txt](/llms.txt). Markdown versions of documentation pages are available by appending `.md` to the page URL.

Use this guide when you run an open-source app on a remote virtual machine (VM).

## 1. Create a host ID for the VM

Before importing credentials, create and persist a stable `ext_agent_host_id` for the VM.

## 2. Complete OAuth locally

A `127.0.0.1` callback reaches the computer running the browser, not the remote VM. Complete OAuth locally with the same tool/client for the same user and workspace you will use on the VM.




## 3. Transfer the protected credentials

Transfer the selected registration's protected credential file to the tool's documented VM path over a secure channel such as SSH. Include its issued `client_id`, `access_token`, `refresh_token`, and other saved metadata such as a retained `id_token`.

Preserve the host ID assigned to the VM when importing the credentials so a copied laptop ID does not overwrite it.

## 4. Let the VM manage token refreshes

Let the VM own later refreshes. Use its own host ID for its next authorization.

This procedure transfers an existing credential session. Host-specific usage attribution and revocation of ChatGPT plan access for transferred sessions are not yet available.