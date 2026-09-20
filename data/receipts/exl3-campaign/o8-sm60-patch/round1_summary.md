# Round 1 -- distilled from exl3_keepgoing.log.gz

## FAILED targets (108)
all_reduce_cpu.cuda.o
all_reduce.cuda.o
barrier.cuda.o
broadcast.cuda.o
exl3_comp_unit_1_cb0.cuda.o
exl3_comp_unit_1_cb1.cuda.o
exl3_comp_unit_1_cb2.cuda.o
exl3_comp_unit_2_cb0.cuda.o
exl3_comp_unit_2_cb1.cuda.o
exl3_comp_unit_2_cb2.cuda.o
exl3_comp_unit_3_cb0.cuda.o
exl3_comp_unit_3_cb1.cuda.o
exl3_comp_unit_3_cb2.cuda.o
exl3_comp_unit_4_cb0.cuda.o
exl3_comp_unit_4_cb1.cuda.o
exl3_comp_unit_4_cb2.cuda.o
exl3_comp_unit_5_cb0.cuda.o
exl3_comp_unit_5_cb1.cuda.o
exl3_comp_unit_5_cb2.cuda.o
exl3_comp_unit_6_cb0.cuda.o
exl3_comp_unit_6_cb1.cuda.o
exl3_comp_unit_6_cb2.cuda.o
exl3_comp_unit_7_cb0.cuda.o
exl3_comp_unit_7_cb1.cuda.o
exl3_comp_unit_7_cb2.cuda.o
exl3_comp_unit_8_cb0.cuda.o
exl3_comp_unit_8_cb1.cuda.o
exl3_comp_unit_8_cb2.cuda.o
exl3_gemm.cuda.o
exl3_gemv.cuda.o
exl3_gemv_int8.cuda.o
exl3_gemv_int8_inst_coop_k1.cuda.o
exl3_gemv_int8_inst_coop_k2.cuda.o
exl3_gemv_int8_inst_coop_k3.cuda.o
exl3_gemv_int8_inst_coop_k4.cuda.o
exl3_gemv_int8_inst_coop_k5.cuda.o
exl3_gemv_int8_inst_coop_k6.cuda.o
exl3_gemv_int8_inst_coop_k7.cuda.o
exl3_gemv_int8_inst_coop_k8.cuda.o
exl3_gemv_int8_inst_sq_k1.cuda.o
exl3_gemv_int8_inst_sq_k2.cuda.o
exl3_gemv_int8_inst_sq_k3.cuda.o
exl3_gemv_int8_inst_sq_k4.cuda.o
exl3_gemv_int8_inst_sq_k5.cuda.o
exl3_gemv_int8_inst_sq_k6.cuda.o
exl3_kernel_map.cuda.o
exl3_moe_coop.cuda.o
exl3_moe_coop_inst_k1.cuda.o
exl3_moe_coop_inst_k2.cuda.o
exl3_moe_coop_inst_k3.cuda.o
exl3_moe_coop_inst_k4.cuda.o
exl3_moe_coop_inst_k5.cuda.o
exl3_moe_coop_inst_k6.cuda.o
exl3_moe_coop_inst_k7.cuda.o
exl3_moe_coop_inst_k8.cuda.o
exl3_moe_inst_k0_n128_cb1.cuda.o
exl3_moe_inst_k0_n128_cb2.cuda.o
exl3_moe_inst_k0_n128_cb2_m32.cuda.o
exl3_moe_inst_k0_n128_cb2_m64.cuda.o
exl3_moe_inst_k0_n256_cb1.cuda.o
exl3_moe_inst_k0_n256_cb2.cuda.o
exl3_moe_inst_k1_cb1.cuda.o
exl3_moe_inst_k1_cb2.cuda.o
exl3_moe_inst_k1_cb2_m32.cuda.o
exl3_moe_inst_k1_cb2_m64.cuda.o
exl3_moe_inst_k2_cb1.cuda.o
exl3_moe_inst_k2_cb2.cuda.o
exl3_moe_inst_k2_cb2_m32.cuda.o
exl3_moe_inst_k2_cb2_m64.cuda.o
exl3_moe_inst_k3_cb1.cuda.o
exl3_moe_inst_k3_cb2.cuda.o
exl3_moe_inst_k3_cb2_m32.cuda.o
exl3_moe_inst_k3_cb2_m64.cuda.o
exl3_moe_inst_k4_cb1.cuda.o
exl3_moe_inst_k4_cb2.cuda.o
exl3_moe_inst_k4_cb2_m32.cuda.o
exl3_moe_inst_k4_cb2_m64.cuda.o
exl3_moe_inst_k5_cb1.cuda.o
exl3_moe_inst_k5_cb2.cuda.o
exl3_moe_inst_k5_cb2_m32.cuda.o
exl3_moe_inst_k5_cb2_m64.cuda.o
exl3_moe_inst_k6_cb1.cuda.o
exl3_moe_inst_k6_cb2.cuda.o
exl3_moe_inst_k6_cb2_m32.cuda.o
exl3_moe_inst_k6_cb2_m64.cuda.o
exl3_moe_inst_k7_cb1.cuda.o
exl3_moe_inst_k7_cb2.cuda.o
exl3_moe_inst_k7_cb2_m32.cuda.o
exl3_moe_inst_k7_cb2_m64.cuda.o
exl3_moe_inst_k8_cb1.cuda.o
exl3_moe_inst_k8_cb2.cuda.o
exl3_moe_inst_k8_cb2_m32.cuda.o
exl3_moe_inst_k8_cb2_m64.cuda.o
gather.cuda.o
hgemm_f16acc.cuda.o
moe_handoff.cuda.o
pack.cuda.o
q_cache.cuda.o
quantize.cuda.o
quantize_tiles_inst_k1.cuda.o
quantize_tiles_inst_k2.cuda.o
quantize_tiles_inst_k3.cuda.o
quantize_tiles_inst_k4.cuda.o
quantize_tiles_inst_k5.cuda.o
quantize_tiles_inst_k6.cuda.o
quantize_tiles_inst_k7.cuda.o
quantize_tiles_inst_k8.cuda.o
reconstruct.cuda.o

## ptxas feature errors (deduped, with counts)
    464 Feature 'mma' requires .target sm_70
    464 Feature '.m16n8k16' requires .target sm_80
    144 Feature 'ldmatrix' requires .target sm_75
    112 Feature 'cp.async' requires .target sm_80
     12 Feature 'cp.async.commit_group' requires .target sm_80
      6 Feature 'cp.async.wait_group' requires .target sm_80

## front-end errors (deduped)
    124 error: identifier "__nanosleep" is undefined
    119 error: identifier "__dp4a" is undefined
