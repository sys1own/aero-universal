// CUDA kernels for the physics simulator.
//
// The Aero semantic mapper registers each `__global__` entry point as a
// `uast_gpu_kernel` node and links launch sites (`<<<...>>>`) to them with the
// special `gpu_kernel` edge type.  The GPU pipeline compiles these with nvcc.

extern "C" __global__ void vector_add(const double *a, const double *b, double *out, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) {
        out[i] = a[i] + b[i];
    }
}

extern "C" __global__ void reduce_sum(const double *in, double *partial, int n) {
    extern __shared__ double sdata[];
    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    sdata[tid] = (i < n) ? in[i] : 0.0;
    __syncthreads();
    for (unsigned int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            sdata[tid] += sdata[tid + s];
        }
        __syncthreads();
    }
    if (tid == 0) {
        partial[blockIdx.x] = sdata[0];
    }
}

// Host launch wrapper (gives the mapper a gpu_kernel edge to resolve).
void launch_vector_add(const double *a, const double *b, double *out, int n) {
    int threads = 256;
    int blocks = (n + threads - 1) / threads;
    vector_add<<<blocks, threads>>>(a, b, out, n);
}
