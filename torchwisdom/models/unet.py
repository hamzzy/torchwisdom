import torch
import torch.nn as nn
import torch.nn.functional as F


__all__ = ['UNet']

# this code is inspired from  milesial repository
# https://github.com/milesial/Pytorch-UNet
# some of the code is taken from that repo and I make changes
# for the thing I need to change


def conv_bn_relu(in_ch, out_ch, ksize=3, padding=1, stride=1):
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, kernel_size=ksize, padding=padding, stride=stride),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True)
    )

def conv_bn_lrelu(in_ch, out_ch, ksize=3, padding=1, stride=1, neg_slope=0.2):
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, kernel_size=ksize, padding=padding, stride=stride),
        nn.BatchNorm2d(out_ch),
        nn.LeakyReLU(inplace=True, negative_slope=neg_slope)
    )

class DoubleConv(nn.Module):
    def __init__(self, in_ch, out_ch, activation='relu'):
        super(DoubleConv, self).__init__()
        if activation=='relu':
            self.conv = nn.Sequential(
                conv_bn_relu(in_ch, out_ch),
                conv_bn_relu(out_ch, out_ch)
            )
        elif activation=='lrelu':
            self.conv = nn.Sequential(
                conv_bn_lrelu(in_ch, out_ch),
                conv_bn_lrelu(out_ch, out_ch)
            )

    def forward(self, x):
        return self.conv(x)

class InConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(InConv, self).__init__()
        self.conv = DoubleConv(in_ch, out_ch)
    def forward(self, x):
        x = self.conv(x)
        return x

class DownConv(nn.Module):
    def __init__(self, in_ch, out_ch, pool='maxpool'):
        super(DownConv, self).__init__()

        if pool=='maxpool':
            self.down = nn.MaxPool2d(2)
        elif pool=='stride':
            self.down = nn.Conv2d(in_ch, in_ch, kernel_size=2, stride=2, padding=1)

        self.conv = DoubleConv(in_ch, out_ch)

    def forward(self, x):
        x = self.down(x)
        x = self.conv(x)
        return x

class UpConv(nn.Module):
    def __init__(self, in_ch, out_ch, mode='bilinear'):
        super(UpConv, self).__init__()
        if mode=='bilinear':
            self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False)
        elif mode=='nearest':
            self.up = nn.Upsample(scale_factor=2, mode='nearest', align_corners=True)
        elif mode=='transpose':
            self.up = nn.ConvTranspose2d(in_ch // 2, in_ch // 2, kernel_size=2, stride=2)

        self.conv = DoubleConv(in_ch, out_ch)

    def _padfix(self, x1, x2):
        # input is CHW
        diffY = x2.size()[2] - x1.size()[2]
        diffX = x2.size()[3] - x1.size()[3]

        x1 = F.pad(x1, (diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2))
        # for padding issues, see
        # https://github.com/HaiyongJiang/U-Net-Pytorch-Unstructured-Buggy/commit/0e854509c2cea854e247a9c615f175f76fbb2e3a
        # https://github.com/xiaopeng-liao/Pytorch-UNet/commit/8ebac70e633bac59fc22bb5195e513d5832fb3bd
        return x1, x2

    def forward(self, x1, x2):
        x1 = self.up(x1)
        x1, x2 = self._padfix(x1, x2)
        x = torch.cat([x1, x2], dim=1)
        x = self.conv(x)
        return x

class OutConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(OutConv, self).__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, kernel_size=1)

    def forward(self, x):
        return self.conv(x)


class UNetEncoder(nn.Module):
    def __init__(self, in_chan, start_feat=64):
        super(UNetEncoder, self).__init__()
        self.out_chan = start_feat * 8
        self.inconv = InConv(in_chan, start_feat)
        self.down1 = DownConv(start_feat, start_feat*2)
        self.down2 = DownConv(start_feat*2, start_feat*4)
        self.down3 = DownConv(start_feat*4, start_feat*8)
        self.down4 = DownConv(start_feat*8, start_feat*8)

    def forward(self, x):
        inc = self.inconv(x)
        dc1 = self.down1(inc)
        dc2 = self.down2(dc1)
        dc3 = self.down3(dc2)
        dc4 = self.down4(dc3)
        return dc4, dc3, dc2, dc1, inc


class UNetDecoder(nn.Module):
    def __init__(self, in_chan, n_classes):
        super(UNetDecoder, self).__init__()
        self.up1 = UpConv(in_chan, in_chan//4)
        self.up2 = UpConv(in_chan//2, in_chan//8)
        self.up3 = UpConv(in_chan//4, in_chan//16)
        self.up4 = UpConv(in_chan//8, in_chan//16)
        self.outconv = OutConv(in_chan//16, n_classes)

    def forward(self, dc4, dc3, dc2, dc1, inc):
        up1 = self.up1(dc4, dc3)
        up2 = self.up2(up1, dc2)
        up3 = self.up3(up2, dc1)
        up4 = self.up4(up3, inc)
        out = self.outconv(up4)
        return out


class UNet(nn.Module):
    def __init__(self, in_chan, n_classes, start_feat=64):
        super(UNet, self).__init__()
        self.encoder_in_chan = in_chan
        self.decoder_in_chan = start_feat * 16
        self.start_feat = start_feat

        self.encoder = UNetEncoder(in_chan=self.encoder_in_chan, start_feat=start_feat)
        self.decoder = UNetDecoder(in_chan=self.decoder_in_chan, n_classes=n_classes)

    def forward(self, x):
        dc4, dc3, dc2, dc1, inc = self.encoder(x)
        out = self.decoder(dc4, dc3, dc2, dc1, inc)
        return out


class TuneableUNetEncoder(nn.Module):
    def __init__(self, in_chan, start_feat=64, deep=4):
        super(TuneableUNetEncoder, self).__init__()
        self.out_chan = start_feat * 8
        self.in_chan = in_chan
        self.start_feat = start_feat
        self.deep = deep
        self.chan = self._generate_chan()
        self.last_chan = self.chan[-1][-1]

        modules = self._make_layer(self.in_chan, self.start_feat)
        self.encoder = nn.Sequential(*modules)

    def _make_layer(self, in_chan, start_feat):
        modules = []
        modules.append(InConv(in_chan, start_feat))
        for d in range(self.deep):
           (in_chan, out_chan) = self.chan[d]
           modules.append(DownConv(in_chan, out_chan))
        return modules

    def _generate_chan(self):
        chan = []
        for d in range(self.deep):
            c1 = 2 ** d
            c2 = 2 ** (d + 1)
            if (d + 1) != self.deep:
                pair = (self.start_feat * c1, self.start_feat * c2)
            else:
                pair = (self.start_feat * c1, self.start_feat * c1)
            chan.append(pair)
        return chan

    def forward(self, x):
        output = []
        for d in range(self.deep+1):
            x = self.encoder[d](x)
            output.append(x)
        return output


class TuneableUNetDecoder(nn.Module):
    def __init__(self, in_chan, n_classes, deep=4):
        super(TuneableUNetDecoder, self).__init__()
        self.in_chan = in_chan
        self.n_classes = n_classes
        self.deep = deep
        self.chan = self._generate_chan()
        self.last_chan = self.chan[-1][-1]

        modules = self._make_layer()
        self.decoder = nn.Sequential(*modules)

    def _make_layer(self):
        modules = []
        for d in range(self.deep):
           (in_chan, out_chan) = self.chan[d]
           modules.append(UpConv(in_chan, out_chan))
        (in_chan, out_chan) = self.chan[self.deep]
        modules.append(OutConv(in_chan, self.n_classes))
        return modules

    def _generate_chan(self):
        chan = []
        self.in_chan = self.in_chan * 2
        for d in range(self.deep):
            c1 = self.in_chan // 2 ** (d)
            if (d + 1) != self.deep:
                c2 = self.in_chan // 2 ** (d + 2)
            else:
                c2 = self.in_chan // 2 ** (d + 1)
            pair = (c1, c2)
            chan.append(pair)

        output_pair = (c2, self.n_classes)
        chan.append(output_pair)
        return chan

    def forward(self, input):
        input.reverse()
        x = self.decoder[0](input[0], input[1])
        for i in range(1, self.deep+1):
            if i+1 != self.deep+1:
                x = self.decoder[i](x, input[i+1])
            else:
                x = self.decoder[self.deep](x)
        return x


class TuneableUNet(nn.Module):
    def __init__(self, in_chan, n_classes, config):
        super(TuneableUNet, self).__init__()
        self.config = config
        self.encoder = TuneableUNetEncoder(
            in_chan=in_chan,
            start_feat=self.config['start_feat'],
            deep=self.config['deep'],
        )

        self.decoder = TuneableUNetDecoder(
            in_chan=self.encoder.last_chan,
            n_classes=n_classes,
            deep=self.config['deep']
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x


if __name__ == '__main__':
    config = {'start_feat': 64, 'deep': 4}
    model = TunnableUNet(in_chan=1, n_classes=1, cfg=config)

    input = torch.rand(1, 1, 224, 224)
    out = model(input)
    print(out)

