_start:
        lui   $sp, 0x8001
        jal   f_main
        nop
        lui   $t0, 0xF000
        sw    $v0, 8($t0)
_halt:
        j     _halt
        nop
f_main:
        addiu $sp, $sp, -8
        sw    $ra, 4($sp)
        sw    $fp, 0($sp)
        addu  $fp, $sp, $zero
        addiu $sp, $sp, -8
L1_while:
        addiu $t0, $zero, 1
        beq   $t0, $zero, L1_wend
        nop
        lui   $t2, 0xF000
        ori   $t2, $t2, 0x0004
        lw    $t0, 0($t2)
        sw    $t0, -4($fp)
        lw    $t0, -4($fp)
        addiu $sp, $sp, -4
        sw    $t0, 0($sp)
        addiu $t0, $zero, 1
        lw    $t1, 0($sp)
        addiu $sp, $sp, 4
        addu  $t0, $t1, $t0
        sw    $t0, -8($fp)
        lw    $t0, -8($fp)
        lui   $t2, 0xF000
        sw    $t0, 0($t2)
        lw    $t0, -8($fp)
        lui   $t2, 0xF000
        ori   $t2, $t2, 0x0008
        sw    $t0, 0($t2)
        beq   $zero, $zero, L1_while
        nop
L1_wend:
L_epi_main:
        addu  $sp, $fp, $zero
        lw    $fp, 0($sp)
        lw    $ra, 4($sp)
        addiu $sp, $sp, 8
        jr    $ra
        nop
