# ------------- c2mips runtime for --target fpga (ADR-009) -------------
# Same nCk algorithm as runtime.s (Spec appendix A, unchanged and still used by --target
# spim), rewritten for openmips / FPGA Studio:
#   - a nop in the delay slot of every branch and jump
#   - real instructions only: li -> addiu / lui+ori, move -> addu, b -> beq $zero, $zero
#   - no .data / la / syscall: a panic writes a code to SEG7 (0xF0000008) and spins at _panic
#       0xDEAD0001 = division by zero (/ and %), 0xDEAD0002 = nCk overflow
# Each "@routine" block is attached only when the program uses it. The emitter removes these
# comments: the output for the IDE has labels and instructions only.

# @routine __rt_nCk
# int nCk(int n, int k)   in: $a0=n $a1=k   out: $v0
# 0 if n<0 || k<0 || k>n ; panic if result > INT_MAX
# r_i = C(n-k+i, i); step: g=gcd(r,i); r=(r/g)*((n-k+i)/(i/g))
# uses only $t0-$t7,$a0,$a1,$v0 (leaf, no stack)
__rt_nCk:
        bltz  $a0, __rt_nCk_zero
        nop
        bltz  $a1, __rt_nCk_zero
        nop
        slt   $t0, $a0, $a1            # n < k ?
        bne   $t0, $zero, __rt_nCk_zero
        nop
        subu  $t1, $a0, $a1            # t1 = n-k
        slt   $t0, $t1, $a1            # n-k < k ?
        beq   $t0, $zero, __rt_nCk_kok
        nop
        addu  $a1, $t1, $zero          # k = min(k, n-k)
__rt_nCk_kok:
        subu  $t1, $a0, $a1            # base = n-k
        addiu $v0, $zero, 1            # r = 1
        addiu $t2, $zero, 1            # i = 1
__rt_nCk_loop:
        slt   $t0, $a1, $t2            # k < i ?
        bne   $t0, $zero, __rt_nCk_ret
        nop
        addu  $t3, $t1, $t2            # num = base + i
        addu  $t4, $v0, $zero          # gcd(r, i) -> $t4
        addu  $t5, $t2, $zero
__rt_nCk_gcd:
        beq   $t5, $zero, __rt_nCk_gcd_end
        nop
        divu  $t4, $t5
        mfhi  $t6
        addu  $t4, $t5, $zero
        addu  $t5, $t6, $zero
        beq   $zero, $zero, __rt_nCk_gcd
        nop
__rt_nCk_gcd_end:
        divu  $v0, $t4
        mflo  $v0                      # r /= g
        divu  $t2, $t4
        mflo  $t7                      # d = i / g
        divu  $t3, $t7
        mflo  $t3                      # num /= d  (exact)
        multu $v0, $t3
        mfhi  $t6
        mflo  $v0                      # r = r * num
        bne   $t6, $zero, __rt_nCk_ovf
        nop
        bltz  $v0, __rt_nCk_ovf        # > INT_MAX
        nop
        addiu $t2, $t2, 1
        beq   $zero, $zero, __rt_nCk_loop
        nop
__rt_nCk_ret:
        jr    $ra
        nop
__rt_nCk_zero:
        addu  $v0, $zero, $zero
        jr    $ra
        nop
__rt_nCk_ovf:
        lui   $t1, 0xDEAD
        ori   $t1, $t1, 0x0002         # nCk overflow
        beq   $zero, $zero, __rt_panic
        nop

# @routine __rt_div0
__rt_div0:
        lui   $t1, 0xDEAD
        ori   $t1, $t1, 0x0001         # division by zero
        beq   $zero, $zero, __rt_panic
        nop

# @routine __rt_panic
# in: $t1 = code; SEG7 = code, then spin
__rt_panic:
        lui   $t0, 0xF000
        sw    $t1, 8($t0)
_panic:
        j     _panic
        nop
