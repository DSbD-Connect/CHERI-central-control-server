<html><head></head><body>

<?php
$post_data = file_get_contents('php://input');
$pairs = explode("&",$post_data);
$MY_POST = array();
foreach ($pairs as $pair){
        $nv = explode("=",$pair);
        $name = urldecode($nv[0]);
        $value = urldecode($nv[1]);
        if($name == "ischeri"){
        	if($value == "cheri"){
        		$action = "index_cheri.php";
        	} else {
        		$action = "index.php";
        	}
        	continue;
        }
        $MY_POST[$name] = $value;
}
?>

<img src="oerc_logo" style="padding-left:0px"/>
<img src="dsbd_logo" style="padding-left:30px"/>
<img src="cyberhive_logo" style="padding-left:30px"/>

<form method="post" action="<?php echo $action; ?>" >
<br/><br/>
<h2>Enter password</h2>
<input name="password" type="text" autocomplete="off" autofocus/><br/><br/>
<input type="submit" value="submit"/>
<?php foreach ($MY_POST as $key => $value) {
echo "<input type=\"hidden\" name=\"".$key."\" value=\"".$value."\" >";
}
?>
</form>

</body></html>
