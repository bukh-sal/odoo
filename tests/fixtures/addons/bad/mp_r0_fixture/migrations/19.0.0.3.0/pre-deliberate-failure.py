def migrate(cr, version):
    cr.execute("UPDATE mp_r0_fixture SET name = 'committed-before-failure'")
    cr.commit()
    raise RuntimeError('MP_R0 deliberate failure after commit')
