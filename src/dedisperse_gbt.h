
typedef struct {
  //float dm_max;
  //float dm_offset;
  int nchan;
  int raw_nchan;
  int ndata;
  float *chans;  //delay in pixels is chan_map[i]*dm
  float *raw_chans; 
  float dt;

  float **raw_data; //remap to float so we can do things like clean up data without worrying about overflow
  float **data;
  int *chan_map;

  //int icur;  //useful if we want to collapse the data after dedispersing
} Data;

int get_nchan_from_depth(int depth);
float get_diagonal_dm_simple(float nu1, float nu2, float dt, int depth);
int *ivector(int n);
size_t get_burst_nextra(size_t ndata2, int depth);
size_t my_burst_dm_transform(float *indata1, float *indata2, float *outdata,size_t ntime1, size_t ntime2, float delta_t,size_t nfreq, int *chan_map, int depth);

Data *read_gbt(const char *fname);
