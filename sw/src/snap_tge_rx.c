#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

#include <string.h> 
#include <sys/types.h> 
#include <sys/socket.h> 
#include <arpa/inet.h> 
#include <netinet/in.h>

#define PORT 10000
#define PACKETS_PER_SPECTRA 4
#define PRINT_PACKETS 4000
#define N_CHANNELS 2048
#define N_STOKES_PER_PACKET 4

typedef struct pkt {
  uint64_t header;
  int32_t data[N_STOKES_PER_PACKET * N_CHANNELS / PACKETS_PER_SPECTRA];
} pkt;

int
main (int argc, char **argv)
{
  char *filename;
  char *source;
  int inttime;
  int acclen;
  float rfc = 3500.0;
  float ifc = 629.1452;
  float samplerate = 900.0;
  int index;
  int c;
  int flip_spectrum = 0;
  int write_fb = 0;
  size_t recv_rv;

  // Loop variables
  int i;
  int starttime;
  int elapsed;
  int wait = 1;
  int header;
  int sub_spectra_index;
  unsigned long spectra_index;
  unsigned long last_spectra_written = -1;
  unsigned long missing_spectra;
  long int last_header;
  int pkt_cnt = 0;
  int bytes = 0;
  struct pkt pkt_buf[1];

  // Spectra buffers
  float spec_xx[N_CHANNELS];
  float spec_yy[N_CHANNELS];
  float spec_i[N_CHANNELS]; // summed xx + yy
  FILE *fxx_p;
  FILE *fyy_p;
  char fname_xx[128];
  char fname_yy[128];

  // Network socket handle
  int sockfd;
  struct sockaddr_in sock;

  opterr = 0;

  while ((c = getopt (argc, argv, "f:t:s:l:a:r:i:FPh")) != -1)
    switch (c)
      {
      case 'f':
        filename = optarg;
        break;
      case 't':
        inttime = atoi(optarg);
        break;
      case 's':
        source = optarg;
        break;
      case 'l':
        acclen = atoi(optarg);
        break;
      case 'a':
        samplerate = atof(optarg);
        break;
      case 'r':
        rfc = atof(optarg);
        break;
      case 'i':
        ifc = atof(optarg);
        break;
      case 'F':
        flip_spectrum = 1;
        break;
      case 'P':
        write_fb = 1;
        break;
      case 'h':
        fprintf(stdout, "  Usage:\n");
        fprintf(stdout, "     snap_tge_rx [flags]\n");
        fprintf(stdout, "   Flags:\n");
        fprintf(stdout, "     -f filename\n");
        fprintf(stdout, "     -t recording time (seconds)\n");
        fprintf(stdout, "     -s source name\n");
        fprintf(stdout, "     -l accumulation length\n");
        fprintf(stdout, "     -a ADC clock rate (MHz)\n");
        fprintf(stdout, "     -r RF center frequency (MHz)\n");
        fprintf(stdout, "     -i IF center frequency (MHz)\n");
        fprintf(stdout, "     -F [use this flag to flip the band]\n");
        fprintf(stdout, "     -P [use this flag to output filterbank files]\n");
        return 0;
        break;
      case '?':
        if (isprint (optopt))
          fprintf (stderr, "Unknown option `-%c'.\n", optopt);
        else
          fprintf (stderr,
                   "Unknown option character `\\x%x'.\n",
                   optopt);
        return 1;
      default:
        abort ();
      }

  fprintf(stdout, "Filename: %s\n", filename);
  fprintf(stdout, "Recording time: %d seconds\n", inttime);
  fprintf(stdout, "Source: %s\n", source);
  fprintf(stdout, "FPGA Accumulation Length: %d spectra\n", acclen);
  fprintf(stdout, "ADC Sampling rate: %f MHz\n", samplerate);
  fprintf(stdout, "RF center frequency: %f MHz\n", rfc);
  fprintf(stdout, "IF center frequency: %f MHz\n", ifc);
  if (flip_spectrum) {
    fprintf(stdout, "Spectrum *WILL* be flipped\n");
  } else {
    fprintf(stdout, "Spectrum *WILL NOT* be flipped\n");
  }

  fprintf(stdout, "\nPacket size: %d bytes\n", (int) sizeof(pkt));
  // Open a socket to receive the data!
  if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 ) { 
      perror("socket creation failed"); 
      exit(EXIT_FAILURE); 
  } 
  
  // Bind socket
  memset(&sock, 0, sizeof(sock));
  sock.sin_family = AF_INET;
  sock.sin_addr.s_addr = htonl(INADDR_ANY);
  sock.sin_port = htons(PORT);
  if (bind(sockfd, (struct sockaddr *) &sock, sizeof(sock))) {
    perror("Error binding UDP socket");
    exit(EXIT_FAILURE); 
  }

  // Open file(s)
  starttime = (int) time(NULL);
  sprintf(fname_xx, "%s_xx_%d.raw", filename, starttime);
  sprintf(fname_yy, "%s_yy_%d.raw", filename, starttime);
  fprintf(stdout, "Writing XX to %s\n", fname_xx);
  fprintf(stdout, "Writing YY to %s\n", fname_yy);
  if ((fxx_p = (FILE *)fopen(fname_xx, "wb")) == NULL) {
    perror("Error opening file");
  }
  if ((fyy_p = (FILE *)fopen(fname_yy, "wb")) == NULL) {
    perror("Error opening file");
  }
  
  while (1) {
    if ((recv_rv = recv(sockfd, pkt_buf, sizeof(pkt), 0) <= 0)) {
      continue;
    }
    header = be64toh(pkt_buf->header);
    sub_spectra_index = header % PACKETS_PER_SPECTRA;
    spectra_index = header / PACKETS_PER_SPECTRA;
    //fprintf(stdout, "H: %lu\n", header);
    // Hold off writing until the start of a spectra
    if (wait) {
      if (sub_spectra_index == 0) {
        wait = 0;
      } else {
        fprintf(stdout, "Waiting for packet for start of spectra\n");
        continue;
      }
    }
    // If this is not the first packet, check that it has come in order
    if (pkt_cnt > 0) {
      if (header != (last_header + 1)) {
        fprintf(stderr, "Missed a packet!\n");
      }
    }

    // Write the packet data to buffers
    if (flip_spectrum) {
      for (i=0; i<(N_CHANNELS / PACKETS_PER_SPECTRA); i++) {
        spec_xx[N_CHANNELS - 1 - (sub_spectra_index*(N_CHANNELS / PACKETS_PER_SPECTRA) + i)] = (float) be32toh(pkt_buf->data[N_STOKES_PER_PACKET*i]);
        spec_yy[N_CHANNELS - 1 - (sub_spectra_index*(N_CHANNELS / PACKETS_PER_SPECTRA) + i)] = (float) be32toh(pkt_buf->data[N_STOKES_PER_PACKET*i + 1]);
      }
    } else {
      for (i=0; i<(N_CHANNELS / PACKETS_PER_SPECTRA); i++) {
        spec_xx[sub_spectra_index*(N_CHANNELS / PACKETS_PER_SPECTRA) + i] = (float) be32toh(pkt_buf->data[N_STOKES_PER_PACKET*i]);
        spec_yy[sub_spectra_index*(N_CHANNELS / PACKETS_PER_SPECTRA) + i] = (float) be32toh(pkt_buf->data[N_STOKES_PER_PACKET*i + 1]);
      }
    }
    
    // If this is the last packet, write it to disk
    if (sub_spectra_index == (PACKETS_PER_SPECTRA - 1)) {
      //for (i=0; i<5; i++) {
      //    fprintf(stdout, "%dx: %f\n", i, spec_xx[i] / 1024.);
      //    fprintf(stdout, "%dy: %f\n", i, spec_yy[i] / 1024.);
      //}
      // Figure out if any spectra are missing and repeat this spectra
      // to compensate. Lazy, but this should very rarely happen.
      if (last_spectra_written > 0) {
        missing_spectra = last_spectra_written - spectra_index;
      }
      for (i=missing_spectra; i>0; i--) {
        fprintf(stderr, "Writing %lu missing spectra\n", missing_spectra);
        fwrite(spec_xx, N_CHANNELS * sizeof(float), 1, fxx_p); 
        fwrite(spec_yy, N_CHANNELS * sizeof(float), 1, fyy_p); 
      }
      fwrite(spec_xx, N_CHANNELS * sizeof(float), 1, fxx_p);
      fwrite(spec_yy, N_CHANNELS * sizeof(float), 1, fyy_p);
      last_spectra_written = spectra_index;
      if (elapsed > inttime) {
        break;
      }
    }

    last_header = header;
    pkt_cnt++;
    elapsed = (int) time(NULL) - starttime;
    if ((pkt_cnt % 1000) == 0) {
        fprintf(stdout, "Received %d packets (%d seconds elapsed)\n", pkt_cnt, elapsed);
    }
  }
  fclose(fxx_p);
  fclose(fyy_p);

  // Write filterbank files
  if (write_fb) {
    char cmd[1024];
    sprintf(cmd, "python /usr/local/bin/snap_append_fb_header.py -s %s -a %d -n %d -f %.8f -r %.8f -i %.8f %s %d",
      source,
      acclen,
      N_CHANNELS,
      samplerate,
      rfc,
      ifc,
      fname_xx,
      starttime
    );
    system(cmd);
  }
  return 0;
}
