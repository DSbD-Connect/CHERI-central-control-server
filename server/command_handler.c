#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>

char** split_string_at(char *, char);
void send_message(char *cmd_msg, char *ip_addr_str);

int check_password(char *password_given){
  int password_good;
  char data_buff[13];
  char text_buff[200];
  char **bits;
  char *correct_hash, *salt;
  FILE *f;

  password_good = 0;

  /* get the salt and the password hash from the password file */
  f = fopen("password", "r");
  fgets(text_buff,200,f);
  fclose(f);
  bits = split_string_at(text_buff,'\n');
  bits = split_string_at(bits[0],' ');
  salt = bits[0];
  correct_hash = bits[1];

  /* concatenate the salt and the given password, and feed it into sha256 */
  strcpy(data_buff,salt);
  strcpy(data_buff+strlen(salt),password_given);
  sprintf(text_buff,"echo %s | sha256sum",data_buff);
  f = popen(text_buff,"r");
  fgets(text_buff,100,f);
  pclose(f);

  /* pull out the sha256 hash of the data and compare it to the stored hash */
  bits = split_string_at(text_buff,' ');
  if(strcmp(bits[0],correct_hash) == 0)
    password_good=1;

  return password_good;
}

int main(int argc, char **argv){  
  char *post_data_str, *server_name;
  char **post_data_bits;
  char *device_name, *ip_addr_str, *cmd_name, *cmd_msg, *cmd_msg_con, *conn_id, *password;
  int data_bits_ind, form_name_ind, n_data_bits, password_ind;
  int total_args_len, cmd_msg_len;
  FILE *logfile;
  
  post_data_str = argv[1];
  server_name = argv[2];

  /* split the POST data string */
  post_data_bits = split_string_at(post_data_str,'&');

  /* parse the necessary values out of the chunks of POST data */
  total_args_len=0;
  for(data_bits_ind=0;post_data_bits[data_bits_ind]!=0;data_bits_ind++){
    char *this_chunk;
    char **bits, **bits2;

    this_chunk = post_data_bits[data_bits_ind];
    bits = split_string_at(this_chunk,'=');
    if (strcmp(bits[0], "form-name") == 0) {
      form_name_ind = data_bits_ind;
      bits2 = split_string_at(bits[1],'|');
      device_name = bits2[0];
      ip_addr_str = bits2[1];
      conn_id = bits2[2];
      cmd_name = bits2[3];
    } else if (strcmp(bits[0], "password") == 0) {
      password_ind = data_bits_ind;
      password = bits[1];
    } else {
      total_args_len += strlen(this_chunk);
    }
  }
  n_data_bits = data_bits_ind;

  if (!check_password(password)) {
    printf("Command Handler: not sending command, bad password\n");
    logfile = fopen("html/command_log", "a");
    fprintf(logfile,"Command Handler: not sending command, bad password\n");
    fclose(logfile);
    return 1;
  }

  /* create the command string to send out */
  cmd_msg_len = 8 + strlen(cmd_name)+strlen(server_name)+strlen(conn_id)+total_args_len+n_data_bits+2;
  /* 8 for COMMAND and the final null char
     n_data_bits+2 for the pipe characters (need three more than number of args,
                                           and n_data_bits is one more than 
                                           number of args) */
  cmd_msg = malloc(cmd_msg_len);
  sprintf(cmd_msg,"COMMAND|%s|%s|%s",server_name,conn_id,cmd_name);
  cmd_msg_con = cmd_msg+10+strlen(cmd_name)+strlen(server_name)+strlen(conn_id);
  for(data_bits_ind=0;post_data_bits[data_bits_ind]!=0;data_bits_ind++){
    char *this_chunk;
    if((data_bits_ind == form_name_ind) || (data_bits_ind == password_ind))
      continue;
    this_chunk = post_data_bits[data_bits_ind];
    sprintf(cmd_msg_con,"|%s",this_chunk);
    cmd_msg_con+= strlen(this_chunk)+1;
  }
  *cmd_msg_con=0;

  /* send the command and log it */
  printf("Command Handler: sending command /%s/ to %s at %s\n",cmd_msg,device_name,ip_addr_str);
  logfile = fopen("html/command_log", "a");
  fprintf(logfile,"Command Handler: sending command /%s/ to %s at %s\n",cmd_msg,device_name,ip_addr_str);
  fclose(logfile);
  send_message(cmd_msg,ip_addr_str);

  return 0;
}

void send_message(char *cmd_msg, char *ip_addr_str){
  int sock;
  struct sockaddr_in addr;

  addr.sin_family      = AF_INET;
  addr.sin_port        = htons(5026);
  addr.sin_addr.s_addr = inet_addr(ip_addr_str);
  
  sock = socket(AF_INET, SOCK_DGRAM, 0);
  sendto(sock, cmd_msg, (strlen(cmd_msg)), 0,
	 (struct sockaddr *)&addr, sizeof(addr));

  close(sock);
}

char** split_string_at(char *str, char delim){
  char **str_bits;
  int n_str_bits, str_bits_ind;
  char *con, *base;
  
  n_str_bits = 1;
  for(con = str; *con != 0; con++)
    if(*con == delim)
      n_str_bits++;
  str_bits = malloc((n_str_bits+1)*sizeof(char*));
  str_bits[n_str_bits] = 0;

  base=con=str;
  str_bits_ind=0;
  while(1){
    if ((*con == delim) || (*con == 0)){
      str_bits[str_bits_ind] = malloc(con-base+1);
      strncpy(str_bits[str_bits_ind], base, con-base);
      str_bits[str_bits_ind][con-base]=0;
      if (*con == 0)
	break;
      str_bits_ind++;
      base=con=con+1;   
    }
    else
      con++;
  }

  return str_bits;
}
