curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(lsb_release -cs).noarmor.gpg | sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/$(lsb_release -cs).tailscale-keyring.list | sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update
sudo apt install tailscale
sudo tailscale up
sudo visudo
exit
sudo whoami
sudo apt update && sudo apt install openssh-server -y
sudo systemctl enable --now ssh
nvtop
sudo apt install nvtop -y
nvtop
nvtop
sudo shutdown
ssh mark@10.0.0.194
nvtop
sudo nano /etc/samba/smb.conf
sudo mkdir -p /var/lib/samba/usershares
sudo groupadd -r sambashare
sudo chown root:sambashare /var/lib/samba/usershares
sudo chmod 1770 /var/lib/samba/usershares
sudo systemctl restart smbd.service nmbd.service
whoami
ls -la ~/.ssh/ ; tail -1 ~/.ssh/authorized_keys   # did the key arrive here?
chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys   # sshd silently rejects keys if perms are loose
sudo journalctl -u ssh -n 5             # will name the exact refusal reason
chmod 755 /home/mark
dir
cd AI
dir
cd ..
cd /mnt/
cd HDD
cd Scripts/
dir
./start_turboquant_qwen36.sh 
nvtop
sudo pkill llama-server
ssh mark@10.0.0.194
nvtop
ssh mark@10.0.0.194
sudo pkill llama-server
cd /mnt/HDD/Scripts
dir
./start_turboquant_qwen36.sh
sudo pkill llama-server
./start_turboquant_qwen36.sh
sudo pkill llama-server
./start_turboquant_qwen36.sh
sudo pkill llama-server
sudo swapoff /mnt/optane/swapfile          # migrates the 2.3GB back; takes a moment
sudo sed -i 's|^/mnt/optane/swapfile|#&|' /etc/fstab
sudo sed -i '/mnt\/optane .*ext4/s/$/ # disabled pending H10 swap/' /etc/fstab  # optional note
sudo umount /mnt/optane
