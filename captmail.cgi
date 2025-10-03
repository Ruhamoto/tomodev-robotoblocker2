#!/usr/local/bin/perl

#┌─────────────────────────────────
#│ Captcha Mail : captmail.cgi - 2019/10/06
#│ copyright (c) kentweb, 1997-2019
#│ http://www.kent-web.com/
#└─────────────────────────────────

# モジュール実行
use strict;
use CGI::Carp qw(fatalsToBrowser);
use lib './lib';
use CGI::Minimal;

# 設定ファイル読み込み
require './init.cgi';
my %cf = set_init();

# データ受理
CGI::Minimal::max_read_size($cf{maxdata});
my $cgi = CGI::Minimal->new;
error('容量オーバー') if ($cgi->truncated);
my ($key,$need,$in) = parse_form();

# フォーム表記
load_form() if (@$key == 0);

# 禁止ワードチェック
if ($cf{no_wd}) { check_word(); }

# ホスト取得＆チェック
my ($host,$addr) = get_host();

# 必須入力チェック
my ($check,@err);
if ($$in{need} || @$need > 0) {
	
	# needフィールドの値を必須配列に加える
	my @tmp = split(/\s+/,$$in{need});
	push(@$need,@tmp);
	
	# 必須配列の重複要素を排除
	my %count;
	@$need = grep {!$count{$_}++} @$need;
	
	# 必須項目の入力値をチェックする
	for (@$need) {
		
		# フィールドの値が投げられてこないもの（ラジオボタン等）
		if (!defined($$in{$_})) {
			$check++;
			push(@$key,$_);
			push(@err,$_);
			
		# 入力なしの場合
		} elsif ($$in{$_} eq "") {
			$check++;
			push(@err,$_);
		}
	}
}

# 入力内容マッチ
my ($match1,$match2);
if ($$in{match}) {
	($match1,$match2) = split(/\s+/,$$in{match},2);
	
	if ($$in{$match1} ne $$in{$match2}) {
		error("$match1と$match2の再入力内容が異なります");
	}
}

# 入力チェック確認画面
if ($check) { err_input($match2); }

# --- プレビュー
if ($$in{mode} ne "send") {
	# 連続送信チェック
	check_post('view');
	
	# 確認画面
	preview();

# --- 送信実行
} else {
	# 連続送信チェック
	check_post('send');
	
	# sendmail送信
	send_mail();
}

#-----------------------------------------------------------
#  フォーム表示
#-----------------------------------------------------------
sub load_form {
	# 画像認証作成
	require $cf{captcha_pl};
	my ($str_plain,$str_crypt) = cap::make($cf{captcha_key},$cf{cap_len});
	
	# テンプレ読み込み
	open(IN,"$cf{tmpldir}/form.html") or error("open err: form.html");
	my $tmpl = join('',<IN>);
	close(IN);
	
	# 文字変換
	$tmpl =~ s/!str_crypt!/$str_crypt/g;
	$tmpl =~ s/!([a-z]+_cgi)!/$cf{$1}/g;
	
	# フォーム表記
	print "Content-type: text/html; charset=utf-8\n\n";
	print footer($tmpl);
	exit;
}

#-----------------------------------------------------------
#  プレビュー
#-----------------------------------------------------------
sub preview {
	# post送信チェック
	if ($cf{postonly} && $ENV{REQUEST_METHOD} ne 'POST') {
		error("不正なアクセスです");
	}
	
	# 送信内容チェック
	error("データを取得できません") if (@$key == 0);
	
	# メール書式チェック
	check_email($$in{email}) if ($$in{email});
	
	# 画像認証チェック
	require $cf{captcha_pl};
	if ($$in{captcha} !~ /^\d{$cf{cap_len}}$/) {
		error("画像認証が入力不備です。<br>投稿フォームに戻って再入力してください");
	}
	
	# 投稿キーチェック
	# -1 : キー不一致
	#  0 : 制限時間オーバー
	#  1 : キー一致
	my $chk = cap::check($$in{captcha},$$in{str_crypt},$cf{captcha_key},$cf{cap_time},$cf{cap_len});
	if ($chk == 0) {
		error("画像認証が制限時間を超過しました。<br>投稿フォームに戻って再読込み後、指定の数字を再入力してください");
	} elsif ($chk == -1) {
		error("画像認証が不正です。<br>投稿フォームに戻って再入力してください");
	}
	
	# 時間取得
	my $time = time;
	
	# 一時ファイル作成
	my $rand = make_tmp($time);
	
	# 順番
	if ($$in{sort}) {
		my (@tmp,%tmp);
		for ( split(/\s+/,$$in{sort}) ) {
			push(@tmp,$_);
			$tmp{$_}++;
		}
		for (@$key) {
			if (!defined($tmp{$_})) { push(@tmp,$_); }
		}
		@$key = @tmp;
	}
	
	# テンプレート読込
	open(IN,"$cf{tmpldir}/conf.html") or error("open err: conf.html");
	my $tmpl = join('',<IN>);
	close(IN);
	
	# テンプレート分割
	my ($head,$loop,$foot) = $tmpl =~ m|(.+)<!-- cell -->(.+)<!-- /cell -->(.+)|s
			? ($1,$2,$3)
			: error("テンプレート不正");
	
	# 引数
	my $hidden =<<EOM;
<input type="hidden" name="mode" value="send">
<input type="hidden" name="tmp_data" value="$rand">
EOM

	# 項目
	my ($bef, $item);
	for my $key (@$key) {
		next if ($bef eq $key);
		next if ($key eq "x");
		next if ($key eq "y");
		next if ($key eq "need");
		next if ($key eq "captcha");
		next if ($key eq "str_crypt");
		next if ($key eq "match");
		next if ($key eq "sort");
		next if ($$in{match} && $key eq $match2);
		
		# name値チェック
		check_key($key) if ($cf{check_key});
		my $val = hex_encode($$in{$key});
		$hidden .= qq|<input type="hidden" name="$key" value="$val">\n|;
		
		# 改行変換
		$$in{$key} =~ s|\t|<br>|g;
		
		my $tmp = $loop;
		if (defined($cf{replace}->{$key})) {
			$tmp =~ s/!key!/$cf{replace}->{$key}/;
		} else {
			$tmp =~ s/!key!/$key/;
		}
		$tmp =~ s/!val!/$$in{$key}/;
		$item .= $tmp;
		
		$bef = $key;
	}
	
	# 文字置換
	for ( $head, $foot ) {
		s/!mail_cgi!/$cf{mail_cgi}/g;
		s/<!-- hidden -->/$hidden/g;
	}
	
	# 画面展開
	print "Content-type: text/html; charset=utf-8\n\n";
	print $head, $item;
	
	# フッタ
	footer($foot);
}

#-----------------------------------------------------------
#  送信実行
#-----------------------------------------------------------
sub send_mail {
	require './lib/jacode.pl';
	
	# post送信チェック
	if ($cf{postonly} && $ENV{REQUEST_METHOD} ne 'POST') {
		error("不正なアクセスです");
	}
	
	# 送信内容チェック
	error("データを取得できません") if (@$key == 0);
	
	# 一時ファイルチェック
	check_tmp();
	
	# メール書式チェック
	check_email($$in{email},'send') if ($$in{email});
	
	# 時間取得
	my ($date1,$date2) = get_time();
	
	# ブラウザ情報
	my $agent = $ENV{HTTP_USER_AGENT};
	$agent =~ s/[<>&"'()+;]//g;
	
	# 本文テンプレ読み込み
	open(IN,"$cf{tmpldir}/mail.txt") or error("open err: mail.txt");
	my $mail = join('',<IN>);
	close(IN);
	
	# 改行
	$mail =~ s/\r\n/\n/g;
	$mail =~ s/\r/\n/g;
	
	# テンプレ変数変換
	$mail =~ s/!date!/$date1/g;
	$mail =~ s/!agent!/$agent/g;
	$mail =~ s/!host!/$host/g;
	
	# コード変換
	$mail = conv_jis($mail);
	
	# 自動返信ありのとき
	my $reply;
	if ($cf{auto_res}) {
		
		# テンプレ
		open(IN,"$cf{tmpldir}/reply.txt") or error("open err: reply.txt");
		$reply = join('',<IN>);
		close(IN);
		
		# 改行
		$reply =~ s/\r\n/\n/g;
		$reply =~ s/\r/\n/g;
		
		# 変数変換
		$reply =~ s/!date!/$date1/g;
		
		# コード変換
		$reply = conv_jis($reply);
	}
	
	# 本文のキーを展開
	my ($bef,$mbody,$log);
	for (@$key) {
		
		# 本文に含めない部分を排除
		next if ($_ eq "mode");
		next if ($_ eq "need");
		next if ($_ eq "match");
		next if ($_ eq "sort");
		next if ($$in{match} && $_ eq $match2);
		next if ($_ eq 'tmp_data');
		next if ($bef eq $_);
		
		# hexデコード
		$$in{$_} = hex_decode($$in{$_});
		
		# name値の名前
		my $key_name;
		if ($cf{replace}->{$_}) {
			$key_name = $cf{replace}->{$_};
		} else {
			$key_name = $_;
		}
		
		# エスケープ
		$$in{$_} =~ s/\.\n/\. \n/g;
		
		# 添付ファイル風の文字列拒否
		$$in{$_} =~ s/Content-Disposition:\s*attachment;.*//ig;
		$$in{$_} =~ s/Content-Transfer-Encoding:.*//ig;
		$$in{$_} =~ s/Content-Type:\s*multipart\/mixed;\s*boundary=.*//ig;
		
		# 改行復元
		$$in{$_} =~ s/\t/\n/g;
		
		# HTMLタグ変換
		$$in{$_} =~ s/&lt;/</g;
		$$in{$_} =~ s/&gt;/>/g;
		$$in{$_} =~ s/&quot;/"/g;
		$$in{$_} =~ s/&#39;/'/g;
		$$in{$_} =~ s/&amp;/&/g;
		
		# 本文内容
		my $tmp;
		if ($$in{$_} =~ /\n/) {
			$tmp = "$key_name = \n$$in{$_}\n";
		} else {
			$tmp = "$key_name = $$in{$_}\n";
		}
		$mbody .= $tmp;
		
		$bef = $_;
	}
	# コード変換
	$mbody = conv_jis($mbody);
	
	# 本文テンプレ内の変数を置き換え
	$mail =~ s/!message!/$mbody/;
	
	# 返信テンプレ内の変数を置き換え
	$reply =~ s/!message!/$mbody/ if ($cf{auto_res});
	
	# メールアドレスがない場合は送信先に置き換え
	my $email = $$in{email} eq '' ? $cf{mailto} : $$in{email};
	
	# MIMEエンコード
	my $sub_me = $$in{subject} ne '' && defined($cf{multi_sub}->{$$in{subject}}) ? $cf{multi_sub}->{$$in{subject}} : $cf{subject};
	$sub_me = mime_unstructured_header($sub_me);
	my $from;
	if ($$in{name}) {
		$$in{name} =~ s/[\r\n]//g;
		$from = mime_unstructured_header("\"$$in{name}\" <$email>");
	} else {
		$from = $email;
	}
	
	# --- 送信内容フォーマット開始
	# ヘッダー
	my $body = "To: $cf{mailto}\n";
	$body .= "From: $from\n";
	$body .= "Subject: $sub_me\n";
	$body .= "MIME-Version: 1.0\n";
	$body .= "Content-type: text/plain; charset=iso-2022-jp\n";
	$body .= "Content-Transfer-Encoding: 7bit\n";
	$body .= "Date: $date2\n";
	$body .= "X-Mailer: $cf{version}\n\n";
	$body .= "$mail\n";
	
	# 返信内容フォーマット
	my $res_body;
	if ($cf{auto_res}) {
		
		# 件名MIMEエンコード
		my $re_sub = mime_unstructured_header($cf{sub_reply});
		
		$res_body .= "To: $email\n";
		$res_body .= "From: $cf{mailto}\n";
		$res_body .= "Subject: $re_sub\n";
		$res_body .= "MIME-Version: 1.0\n";
		$res_body .= "Content-type: text/plain; charset=iso-2022-jp\n";
		$res_body .= "Content-Transfer-Encoding: 7bit\n";
		$res_body .= "Date: $date2\n";
		$res_body .= "X-Mailer: $cf{version}\n\n";
		$res_body .= "$reply\n";
	}
	
	# senmdailコマンド
	my $scmd = $cf{send_fcmd} ? "$cf{sendmail} -t -i -f $email" : "$cf{sendmail} -t -i";
	
	# 本文送信
	open(MAIL,"| $scmd") or error("メール送信失敗");
	print MAIL "$body\n";
	close(MAIL);
	
	# 返信送信
	if ($cf{auto_res}) {
		my $scmd = $cf{send_fcmd} ? "$cf{sendmail} -t -i -f $cf{mailto}" : "$cf{sendmail} -t -i";
		
		open(MAIL,"| $scmd") or error("メール送信失敗");
		print MAIL "$res_body\n";
		close(MAIL);
	}
	
	# リロード
	if ($cf{reload}) {
		if ($ENV{PERLXS} eq "PerlIS") {
			print "HTTP/1.0 302 Temporary Redirection\r\n";
			print "Content-type: text/html\n";
		}
		print "Location: $cf{back}\n\n";
		exit;
	
	# 完了メッセージ
	} else {
		open(IN,"$cf{tmpldir}/thanks.html") or error("open err: thanks.html");
		my $tmpl = join('',<IN>);
		close(IN);
		
		# 表示
		print "Content-type: text/html; charset=utf-8\n\n";
		$tmpl =~ s/!back!/$cf{back}/g;
		footer($tmpl);
	}
}

#-----------------------------------------------------------
#  入力エラー表示
#-----------------------------------------------------------
sub err_input {
	my $match2 = shift;
	
	# 順番
	if ($$in{sort}) {
		my (@tmp,%tmp);
		for ( split(/\s+/,$$in{sort}) ) {
			push(@tmp,$_);
			$tmp{$_}++;
		}
		for (@$key) {
			if (!defined $tmp{$_}) { push(@tmp,$_); }
		}
		@$key = @tmp;
	}
	
	# テンプレート読み込み
	open(IN,"$cf{tmpldir}/error.html") or die;
	my $tmpl = join('',<IN>);
	close(IN);
	
	# テンプレート分割
	my ($head,$loop,$foot) = $tmpl =~ m|(.+)<!-- cell -->(.+)<!-- /cell -->(.+)|s
			? ($1,$2,$3)
			: error("テンプレート不正");
	
	# ヘッダ
	print "Content-type: text/html; charset=utf-8\n\n";
	print $head;
	
	# 内容展開
	my $bef;
	for my $key (@$key) {
		next if ($key eq "need");
		next if ($key eq "match");
		next if ($key eq "sort");
		next if ($$in{match} && $key eq $match2);
		next if ($bef eq $key);
		next if ($key eq "x");
		next if ($key eq "y");
		next if ($key eq "subject");
		next if ($key eq "captcha");
		next if ($key eq "str_crypt");
		
		my $key_name = defined($cf{replace}->{$key}) ? $cf{replace}->{$key} : $key;
		my $tmp = $loop;
		$tmp =~ s/!key!/$key_name/;
		
		my $erflg;
		for my $err (@err) {
			if ($err eq $key) {
				$erflg++;
				last;
			}
		}
		# 入力なし
		if ($erflg) {
			$tmp =~ s/!val!/<span class="msg">$key_nameは入力必須です.<\/span>/;
		
		# 正常
		} else {
			$$in{$key} =~ s/\t/<br \/>/g;
			$tmp =~ s/!val!/$$in{$key}/;
		}
		print $tmp;
		
		$bef = $key;
	}
	
	# フッタ
	print $foot;
	exit;
}

#-----------------------------------------------------------
#  フォームデコード
#-----------------------------------------------------------
sub parse_form {
	my (@key,@need,%in);
	for my $key ( $cgi->param() ) {
		
		# 複数値の場合はスペースで区切る
		my $val = join(" ", $cgi->param($key));
		
		# 無害化/改行変換
		$key =~ s/[<>&"'\r\n]//g;
		$val =~ s/&/&amp;/g;
		$val =~ s/</&lt;/g;
		$val =~ s/>/&gt;/g;
		$val =~ s/"/&quot;/g;
		$val =~ s/'/&#39;/g;
		$val =~ s/\r\n/\t/g;
		$val =~ s/\r/\t/g;
		$val =~ s/\n/\t/g;
		
		# 入力必須
		if ($key =~ /^_(.+)/) {
			$key = $1;
			push(@need,$key);
		}
		
		# 受け取るキーの順番を覚えておく
		push(@key,$key);
		
		# %inハッシュに代入
		$in{$key} = $val;
	}
	
	# リファレンスで返す
	return (\@key,\@need,\%in);
}

#-----------------------------------------------------------
#  エラー処理
#-----------------------------------------------------------
sub error {
	my $err = shift;
	
	open(IN,"$cf{tmpldir}/error.html") or die;
	my $tmpl = join('',<IN>);
	close(IN);
	
	# 文字置き換え
	$tmpl =~ s/!key!/エラー内容/g;
	$tmpl =~ s|!val!|<span class="msg">$err</span>|g;
	
	print "Content-type: text/html; charset=utf-8\n\n";
	print $tmpl;
	exit;
}

#-----------------------------------------------------------
#  時間取得
#-----------------------------------------------------------
sub get_time {
	$ENV{TZ} = "JST-9";
	my ($sec,$min,$hour,$mday,$mon,$year,$wday) = localtime(time);
	my @week  = qw|Sun Mon Tue Wed Thu Fri Sat|;
	my @month = qw|Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec|;
	
	# 日時のフォーマット
	my $date1 = sprintf("%04d/%02d/%02d(%s) %02d:%02d:%02d",
			$year+1900,$mon+1,$mday,$week[$wday],$hour,$min,$sec);
	my $date2 = sprintf("%s, %02d %s %04d %02d:%02d:%02d",
			$week[$wday],$mday,$month[$mon],$year+1900,$hour,$min,$sec) . " +0900";
	
	return ($date1,$date2);
}

#-----------------------------------------------------------
#  ホスト名取得
#-----------------------------------------------------------
sub get_host {
	# ホスト名取得
	my $h = $ENV{REMOTE_HOST};
	my $a = $ENV{REMOTE_ADDR};
	
	if ($cf{gethostbyaddr} && ($h eq "" || $h eq $a)) {
		$h = gethostbyaddr(pack("C4", split(/\./, $a)), 2);
	}
	if ($h eq "") { $h = $a; }
	
	# チェック
	if ($cf{denyhost}) {
		my $flg;
		foreach ( split(/\s+/, $cf{denyhost}) ) {
			s/\./\\\./g;
			s/\*/\.\*/g;
			
			if ($h =~ /$_/i) { $flg++; last; }
		}
		if ($flg) { error("アクセスを許可されていません"); }
	}
	
	return ($h,$a);
}

#-----------------------------------------------------------
#  送信チェック
#-----------------------------------------------------------
sub check_post {
	my $job = shift;
	
	# 時間取得
	my $now = time;
	
	# ログオープン
	open(DAT,"+< $cf{logfile}") or error("open err: $cf{logfile}");
	eval "flock(DAT,2);";
	my $data = <DAT>;
	
	# 分解
	my ($ip,$time) = split(/<>/,$data);
	
	# IP及び時間をチェック
	if ($ip eq $addr && $now - $time <= $cf{block_post}) {
		close(DAT);
		error("連続送信は$cf{block_post}秒間お待ちください");
	}
	
	# 送信時は保存
	if ($job eq "send") {
		seek(DAT,0,0);
		print DAT "$addr<>$now";
		truncate(DAT,tell(DAT));
	}
	close(DAT);
}

#-----------------------------------------------------------
#  フッター
#-----------------------------------------------------------
sub footer {
	my $foot = shift;
	
	# 著作権表記（削除・改変禁止）
	my $copy = <<EOM;
<p style="text-align:center;font-size:10px;font-family:Verdana,Helvetica,Arial;margin-top:3em;">
	- <a href="http://www.kent-web.com/" target="_top">CaptchaMail</a> -
</p>
EOM

	if ($foot =~ /(.+)(<\/body[^>]*>.*)/si) {
		print "$1$copy$2\n";
	} else {
		print "$foot$copy\n";
		print "</body></html>\n";
	}
	exit;
}

#-----------------------------------------------------------
#  一時ファイル作成
#-----------------------------------------------------------
sub make_tmp {
	my $time = shift;
	
	# 文字候補
	my @wd = (0 .. 9, 'a' .. 'z', 'A' .. 'Z');
	
	# 乱数
	my $rand;
	srand;
	for (1 .. 20) { $rand .= $wd[int(rand(@wd))]; }
	
	# 一時ディレクトリに書き込み
	open(TMP,"+> $cf{tmpdir}/$rand.dat") or error("write err: $rand.dat");
	print TMP $time;
	close(TMP);
	
	return $rand;
}

#-----------------------------------------------------------
#  一時ファイルチェック
#-----------------------------------------------------------
sub check_tmp {
	# データ整合性
	if ($$in{tmp_data} !~ /^[0-9a-zA-Z]{20}$/ || !-e "$cf{tmpdir}/$$in{tmp_data}.dat") {
		error("不正なアクセスです!");
	}
	
	# 時間チェック
	open(IN,"$cf{tmpdir}/$$in{tmp_data}.dat") or error("open err: $$in{tmp_data}.dat");
	my $data = <IN>;
	close(IN);
	
	if (time - $data > 60*60) { error("時間超過のため処理を中断します"); }
	
	# 一時ファイル削除
	unlink("$cf{tmpdir}/$$in{tmp_data}.dat");
	
	# ゴミ掃除
	my $time = time;
	opendir(DIR,"$cf{tmpdir}");
	while( $_ = readdir(DIR) ) {
		next if (!/^\w+\.dat$/);
		
		# 60分以上経過は削除
		my $mtime = (stat("$cf{tmpdir}/$_"))[9];
		if ($time - $mtime > 3600) {
			unlink("$cf{tmpdir}/$_");
		}
	}
	closedir(DIR);
}

#-----------------------------------------------------------
#  hexエンコード
#-----------------------------------------------------------
sub hex_encode {
	my $str = shift;
	
	$str =~ s/(.)/unpack('H2', $1)/eg;
	$str =~ s/\n/\t/g;
	return $str;
}

#-----------------------------------------------------------
#  hexデコード
#-----------------------------------------------------------
sub hex_decode {
	my $str = shift;
	
	$str =~ s/\t/\n/g;
	$str =~ s/([0-9A-Fa-f]{2})/pack('H2', $1)/eg;
	return $str;
}

#-----------------------------------------------------------
#  電子メール書式チェック
#-----------------------------------------------------------
sub check_email {
	my ($eml,$job) = @_;
	
	# 送信時はhexデコード
	if ($job eq 'send') { $eml = hex_decode($eml); }
	
	# E-mail書式チェック
	if ($eml =~ /\,/) {
		error("メールアドレスにコンマ ( , ) が含まれています");
	}
	if ($eml ne '' && $eml !~ /^[\w\.\-]+\@[\w\.\-]+\.[a-zA-Z]{2,6}$/) {
		error("メールアドレスの書式が不正です");
	}
}

#-----------------------------------------------------------
#  name値チェック
#-----------------------------------------------------------
sub check_key {
	my $key = shift;
	
	if ($key !~ /^(?:[0-9a-zA-Z_-]|[\xE0-\xEF][\x80-\xBF]{2})+$/) {
		error("name値に不正な文字が含まれています");
	}
}

#-----------------------------------------------------------
#  禁止ワードチェック
#-----------------------------------------------------------
sub check_word {
	my $flg;
	for (@$key) {
		for my $wd ( split(/,/,$cf{no_wd}) ) {
			if (index($$in{$_},$wd) >= 0) {
				$flg++;
				last;
			}
		}
		if ($flg) { error("禁止ワードが含まれています"); }
	}
}

#-----------------------------------------------------------
#  JISコード変換
#-----------------------------------------------------------
sub conv_jis {
	my $text = shift;
	
	my $ret;
	for my $tmp ( split(/\n/,$text) ) {
		jcode::convert(\$tmp,'jis','utf8');
		$ret .= "$tmp\n";
	}
	$ret;
}

#-----------------------------------------------------------
#  mimeエンコード
#  [quote] http://www.din.or.jp/~ohzaki/perl.htm#JP_Base64
#-----------------------------------------------------------
sub mime_unstructured_header {
  my $oldheader = shift;
  jcode::convert(\$oldheader,'euc','utf8');
  my ($header,@words,@wordstmp,$i);
  my $crlf = $oldheader =~ /\n$/;
  $oldheader =~ s/\s+$//;
  @wordstmp = split /\s+/, $oldheader;
  for ($i = 0; $i < $#wordstmp; $i++) {
    if ($wordstmp[$i] !~ /^[\x21-\x7E]+$/ and
	$wordstmp[$i + 1] !~ /^[\x21-\x7E]+$/) {
      $wordstmp[$i + 1] = "$wordstmp[$i] $wordstmp[$i + 1]";
    } else {
      push(@words, $wordstmp[$i]);
    }
  }
  push(@words, $wordstmp[-1]);
  foreach my $word (@words) {
    if ($word =~ /^[\x21-\x7E]+$/) {
      $header =~ /(?:.*\n)*(.*)/;
      if (length($1) + length($word) > 76) {
	$header .= "\n $word";
      } else {
	$header .= $word;
      }
    } else {
      $header = add_encoded_word($word, $header);
    }
    $header =~ /(?:.*\n)*(.*)/;
    if (length($1) == 76) {
      $header .= "\n ";
    } else {
      $header .= ' ';
    }
  }
  $header =~ s/\n? $//mg;
  $crlf ? "$header\n" : $header;
}
sub add_encoded_word {
  my ($str, $line) = @_;
  my $result;
  my $ascii = '[\x00-\x7F]';
  my $twoBytes = '[\x8E\xA1-\xFE][\xA1-\xFE]';
  my $threeBytes = '\x8F[\xA1-\xFE][\xA1-\xFE]';
  while (length($str)) {
    my $target = $str;
    $str = '';
    if (length($line) + 22 +
	($target =~ /^(?:$twoBytes|$threeBytes)/o) * 8 > 76) {
      $line =~ s/[ \t\n\r]*$/\n/;
      $result .= $line;
      $line = ' ';
    }
    while (1) {
      my $encoded = '=?ISO-2022-JP?B?' .
      b64encode(jcode::jis($target,'euc','z')) . '?=';
      if (length($encoded) + length($line) > 76) {
	$target =~ s/($threeBytes|$twoBytes|$ascii)$//o;
	$str = $1 . $str;
      } else {
	$line .= $encoded;
	last;
      }
    }
  }
  $result . $line;
}
# [quote] http://www.tohoho-web.com/perl/encode.htm
sub b64encode {
    my $buf = shift;
    my ($mode,$tmp,$ret);
    my $b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                . "abcdefghijklmnopqrstuvwxyz"
                . "0123456789+/";

    $mode = length($buf) % 3;
    if ($mode == 1) { $buf .= "\0\0"; }
    if ($mode == 2) { $buf .= "\0"; }
    $buf =~ s/(...)/{
        $tmp = unpack("B*", $1);
        $tmp =~ s|(......)|substr($b64, ord(pack("B*", "00$1")), 1)|eg;
        $ret .= $tmp;
    }/eg;
    if ($mode == 1) { $ret =~ s/..$/==/; }
    if ($mode == 2) { $ret =~ s/.$/=/; }
    
    return $ret;
}

