import { bold, link } from "./bot-util";

export const t = {
	urlReminder: "You need to send an URL to download stuff.",
	maintenanceNotice:
		"Bot is currently under maintenance, it'll return shortly.",
	processing: "Processing...",
	deniedMessage: [
		bold("Introducing Downtify – Your Ultimate Video Downloader 📱✨"),
		"",
		"Say goodbye to the hassle of downloading videos from YouTube, TikTok, and Instagram! With Downtify, you can easily and quickly download videos with just a link. It’s simple, fast, and convenient!",
		"",
		bold("Why Choose Downtify?"),
		"",
		bold(
			`✅ Fast and seamless video downloads  
✅ Supports YouTube, TikTok, and Instagram  
✅ Easy to use – just send the link!  
✅ Private and secure – only available to subscribers  
✅ All videos are downloaded watermark-free`
		),
		"",
		bold("Subscription Details"),
		`Access to all features for just 60⭐️ monthly.  
Enjoy unlimited downloads and exclusive support!`,
		"",
		bold("How to Pay?"),
		"Visit our official news channel @Downtify_news and pay the subscription fee. Once the payment is complete, your access to the bot will be activated.",
		"",
		"Join thousands of satisfied users and experience the convenience yourself!"
	].join("\n"),
};

// https://github.com/yt-dlp/yt-dlp/issues/9506#issuecomment-2053987537
export const tiktokArgs = [
	"--extractor-args",
	"tiktok:api_hostname=api16-normal-c-useast1a.tiktokv.com;app_info=7355728856979392262",
];
