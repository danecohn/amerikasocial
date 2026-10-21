# Sourced by startplasma. Only the Amerika (Plasma) session sets AMERIKA_PLASMA, so the
# stock Plasma session keeps using the stock shell.
if [ "$AMERIKA_PLASMA" = "1" ]; then
    export PLASMA_DEFAULT_SHELL=org.amerika.shell
    export AMERIKA_PLASMA=1
fi
