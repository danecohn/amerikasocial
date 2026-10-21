# Sourced by startplasma. Only the Amerika session sets AMERIKA_SESSION, so the
# stock Plasma session keeps using the stock shell.
if [ "$AMERIKA_SESSION" = "1" ]; then
    export PLASMA_DEFAULT_SHELL=org.amerika.shell
    export AMERIKA_SESSION=1
fi
