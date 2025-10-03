#!/usr/local/bin/perl

#┌─────────────────────────────────
#│ Captcha Mail : check.cgi - 2019/10/06
#│ copyright (c) KentWeb, 1997-2019
#│ http://www.kent-web.com/
#└─────────────────────────────────

# モジュール宣言
use strict;
use CGI::Carp qw(fatalsToBrowser);

# 外部ファイル取り込み
require './init.cgi';
my %cf = set_init();

print <<EOM;
Content-type: text/html; charset=utf-8

<!doctype html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>Check Mode</title>
</head>
<body>
<b>Check Mode: [ $cf{version} ]</b>
<ul>
<li>Perlバージョン : $]
EOM

# ログファイル
if (-f $cf{logfile}) {
	print "<li>ログファイルパス : OK\n";
	
	if (-r $cf{logfile} && -w $cf{logfile}) {
		print "<li>ログファイルパーミッション : OK\n";
	} else {
		print "<li>ログファイルパーミッション : NG\n";
	}
}

# 一時ディレクトリ
if (-d $cf{tmpdir}) {
	print "<li>一時ディレクトリパス : OK\n";
	
	if (-r $cf{tmpdir} && -w $cf{tmpdir} && -x $cf{tmpdir}) {
		print "<li>一時ディレクトリパーミッション : OK\n";
	} else {
		print "<li>一時ディレクトリパーミッション : NG\n";
	}
} else {
	print "<li>一時ディレクトリパス : NG\n";
}

# メールソフトチェック
if (-e $cf{sendmail}) {
	print "<li>sendmailパス : OK\n";
} else {
	print "<li>sendmailパス : NG → $cf{sendmail}\n";
}

# テンプレート
foreach (qw(conf.html error.html thanks.html form.html mail.txt reply.txt)) {
	print "<li>テンプレート ( $_ ) : ";
	
	if (-f "$cf{tmpldir}/$_") {
		print "パスOK\n";
	} else {
		print "パスNG\n";
	}
}

# Image-Magick動作確認
eval { require Image::Magick; };
if ($@) {
	print "<li>Image-Magick動作 : NG\n";
} else {
	print "<li>Image-Magick動作 : OK\n";
}

print <<EOM;
</ul>
</body>
</html>
EOM
exit;

