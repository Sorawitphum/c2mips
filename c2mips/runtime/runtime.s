# ---------------- c2mips runtime (v0.1) ----------------
        .data
__rt_msg_div0:    .asciiz "runtime error: division by zero\n"
__rt_msg_nckovf:  .asciiz "runtime error: nCk overflow\n"
        .text
# int nCk(int n, int k)   in: $a0=n $a1=k   out: $v0
# 0 if n<0 || k<0 || k>n ; panic if result > INT_MAX
# r_i = C(n-k+i, i); step: g=gcd(r,i); r=(r/g)*((n-k+i)/(i/g))
# uses only $t0-$t7,$a0,$a1,$v0 (leaf, no stack)
__rt_nCk:
        bltz  $a0, __rt_nCk_zero
        bltz  $a1, __rt_nCk_zero
        slt   $t0, $a0, $a1            # n < k ?
        bne   $t0, $zero, __rt_nCk_zero
        subu  $t1, $a0, $a1            # t1 = n-k
        slt   $t0, $t1, $a1            # n-k < k ?
        beq   $t0, $zero, __rt_nCk_kok
        move  $a1, $t1                 # k = min(k, n-k)
__rt_nCk_kok:
        subu  $t1, $a0, $a1            # base = n-k
        li    $v0, 1                   # r = 1
        li    $t2, 1                   # i = 1
__rt_nCk_loop:
        slt   $t0, $a1, $t2            # k < i ?
        bne   $t0, $zero, __rt_nCk_ret
        addu  $t3, $t1, $t2            # num = base + i
        move  $t4, $v0                 # gcd(r, i) -> $t4
        move  $t5, $t2
__rt_nCk_gcd:
        beq   $t5, $zero, __rt_nCk_gcd_end
        divu  $t4, $t5
        mfhi  $t6
        move  $t4, $t5
        move  $t5, $t6
        b     __rt_nCk_gcd
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
        bltz  $v0, __rt_nCk_ovf        # > INT_MAX
        addiu $t2, $t2, 1
        b     __rt_nCk_loop
__rt_nCk_ret:
        jr    $ra
__rt_nCk_zero:
        move  $v0, $zero
        jr    $ra
__rt_nCk_ovf:
        la    $a0, __rt_msg_nckovf
        b     __rt_panic
__rt_div0:
        la    $a0, __rt_msg_div0
__rt_panic:
        li    $v0, 4                   # print_string
        syscall
        li    $a0, 70                  # EX_SOFTWARE
        li    $v0, 17                  # exit2
        syscall
