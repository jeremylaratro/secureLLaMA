sudo dnf install docker virt-manager qemu nvidia-container-toolkit bubblewrap
curl -sfL https://raw.githubusercontent.com/Bearer/bearer/main/contrib/install.sh | sh


echo -e 'Install on VM:\n
sudo systemctl enable auditd\n
sudo dnf install xtables-addons xtables-addons-kmod\n
'
