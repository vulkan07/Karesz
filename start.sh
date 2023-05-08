if [ $USER == "karbot" ]
then	
	cd /home/karbot/KarBot
	tmux kill-session
	tmux new-session -d "python KarBot.py"
	echo Bot Started...
else
	echo Script must be run as karbot, not as $USER!
fi	
